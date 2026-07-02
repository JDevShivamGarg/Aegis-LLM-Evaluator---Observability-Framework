import jwt
import datetime
import hashlib
import os
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from src.core.config import settings
from src.core.database import get_db
from src.core.models import User, UserProjectRole

security = HTTPBearer()

def hash_password(password: str) -> str:
    """Computes a secure SHA256 PBKDF2 hash of the password."""
    salt = os.getenv("AUTH_SALT", "aegis_default_salt_change_in_production")
    key = hashlib.pbkdf2_hmac(
        'sha256', 
        password.encode('utf-8'), 
        salt.encode('utf-8'), 
        100000
    )
    return key.hex()

def verify_password(password: str, hashed: str) -> bool:
    """Verifies a password against its hash."""
    return hash_password(password) == hashed

def create_jwt_token(payload: dict, expires_in: int = None) -> str:
    """Generates a signed JWT token containing custom claims."""
    if expires_in is None:
        expires_in = settings.JWT_EXPIRY_SECONDS
        
    claims = payload.copy()
    claims["exp"] = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(seconds=expires_in)
    return jwt.encode(claims, settings.JWT_SECRET, algorithm="HS256")

def decode_jwt_token(token: str) -> dict:
    """Decodes and validates a JWT token; raises HTTPException if invalid or expired."""
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid auth credentials"
        )

def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Dependency that returns the current authenticated user."""
    payload = decode_jwt_token(credentials.credentials)
    username = payload.get("sub")
    if not username:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload invalid"
        )
    user = db.query(User).filter(User.username == username).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    return user

class RequireRole:
    """Dependency class to authorize users based on project roles."""
    def __init__(self, allowed_roles: list[str]):
        self.allowed_roles = allowed_roles

    def __call__(
        self,
        project_id: str,
        user: User = Depends(get_current_user),
        db: Session = Depends(get_db)
    ) -> str:
        # Resolve user's role on the project
        role_entry = db.query(UserProjectRole).filter(
            UserProjectRole.user_id == user.id,
            UserProjectRole.project_id == project_id
        ).first()

        role = role_entry.role if role_entry else "viewer"
        
        # Check if the user's role is allowed
        if role not in self.allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access denied. Required roles: {self.allowed_roles}"
            )
        return role

def check_user_role(db: Session, user: User, project_id: str, allowed_roles: list[str]) -> str:
    """Helper function to perform database role checks dynamically in route logic."""
    role_entry = db.query(UserProjectRole).filter(
        UserProjectRole.user_id == user.id,
        UserProjectRole.project_id == project_id
    ).first()
    
    role = role_entry.role if role_entry else "viewer"
    if role not in allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Access denied. Required roles: {allowed_roles}"
        )
    return role
