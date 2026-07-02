import uuid
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
from fastapi import FastAPI, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.orm import Session
from src.core.database import get_db
from src.core import models
from src.workers.celery_app import test_task
from src.core.auth import (
    hash_password,
    verify_password,
    create_jwt_token,
    get_current_user,
    check_user_role
)

app = FastAPI(
    title="Aegis API Server",
    description="Self-Hosted LLM Evaluation & Observability Framework API",
    version="1.0.0"
)

# === Pydantic Request Models ===

class UserAuthSchema(BaseModel):
    username: str
    password: str
    email: Optional[str] = None

class ProjectRoleAssign(BaseModel):
    username: str
    role: str # 'admin', 'editor', 'viewer'

class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = None

class SuiteCreate(BaseModel):
    name: str
    description: Optional[str] = None

class CaseCreate(BaseModel):
    input_prompt: str
    expected_output: Optional[str] = None
    assertion_rules: Optional[List[Dict[str, Any]]] = []

class BatchCasesCreate(BaseModel):
    cases: List[CaseCreate]

class RunCreate(BaseModel):
    suite_id: str
    model_name: str
    prompt_version: str

# === Auth Routes ===

@app.post("/v1/auth/register", status_code=201)
def register_user(payload: UserAuthSchema, db: Session = Depends(get_db)):
    existing = db.query(models.User).filter(models.User.username == payload.username).first()
    if existing:
        raise HTTPException(status_code=400, detail="Username already exists")
        
    user = models.User(
        id=uuid.uuid4(),
        username=payload.username,
        password_hash=hash_password(payload.password),
        email=payload.email
    )
    db.add(user)
    db.commit()
    return {"message": "User registered successfully", "username": user.username}

@app.post("/v1/auth/login")
def login_user(payload: UserAuthSchema, db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.username == payload.username).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")
        
    token = create_jwt_token({"sub": user.username})
    return {"access_token": token, "token_type": "bearer"}

# === API Route Handlers ===

@app.get("/")
def read_root():
    return {"message": "Welcome to Aegis LLM Evaluation Server"}

@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
    
    return {
        "status": "healthy",
        "database": db_status
    }

@app.post("/v1/projects", status_code=201)
def create_project(
    payload: ProjectCreate, 
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user)
):
    db_project = db.query(models.Project).filter(models.Project.name == payload.name).first()
    if db_project:
        raise HTTPException(status_code=400, detail="Project with this name already exists")
    
    project = models.Project(
        id=uuid.uuid4(),
        name=payload.name,
        description=payload.description
    )
    db.add(project)
    db.flush()
    
    # Auto-assign creator as Project admin
    role_entry = models.UserProjectRole(
        id=uuid.uuid4(),
        user_id=user.id,
        project_id=project.id,
        role="admin"
    )
    db.add(role_entry)
    db.commit()
    db.refresh(project)
    
    return {
        "id": str(project.id),
        "name": project.name,
        "description": project.description,
        "created_at": project.created_at
    }
@app.post("/v1/projects/{project_id}/roles")
def assign_project_role(
    project_id: str, 
    payload: ProjectRoleAssign, 
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user)
):
    try:
        proj_uuid = uuid.UUID(project_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid project UUID format")
        
    # Check if target user exists
    target_user = db.query(models.User).filter(models.User.username == payload.username).first()
    if not target_user:
        raise HTTPException(status_code=404, detail="Target user not found")
        
    # Enforce that only project Admins can assign roles
    check_user_role(db, user, project_id, ["admin"])
    
    # Check valid role values
    if payload.role not in ["admin", "editor", "viewer"]:
        raise HTTPException(status_code=400, detail="Invalid role. Must be admin, editor, or viewer")
        
    # Create or update role
    role_entry = db.query(models.UserProjectRole).filter(
        models.UserProjectRole.user_id == target_user.id,
        models.UserProjectRole.project_id == proj_uuid
    ).first()
    
    if role_entry:
        role_entry.role = payload.role
    else:
        role_entry = models.UserProjectRole(
            id=uuid.uuid4(),
            user_id=target_user.id,
            project_id=proj_uuid,
            role=payload.role
        )
        db.add(role_entry)
        
    db.commit()
    return {"message": f"Successfully assigned role {payload.role} to user {payload.username}"}

@app.post("/v1/projects/{project_id}/suites", status_code=201)
def create_suite(
    project_id: str, 
    payload: SuiteCreate, 
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user)
):
    try:
        proj_uuid = uuid.UUID(project_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid project UUID format")
        
    project = db.query(models.Project).filter(models.Project.id == proj_uuid).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
        
    # Enforce role verification
    check_user_role(db, user, project_id, ["admin", "editor"])
    
    suite = models.TestSuite(
        id=uuid.uuid4(),
        project_id=proj_uuid,
        name=payload.name,
        description=payload.description
    )
    db.add(suite)
    db.commit()
    db.refresh(suite)
    return {
        "id": str(suite.id),
        "project_id": str(suite.project_id),
        "name": suite.name,
        "description": suite.description,
        "created_at": suite.created_at
    }

@app.post("/v1/suites/{suite_id}/cases", status_code=201)
def upload_cases(
    suite_id: str, 
    payload: BatchCasesCreate, 
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user)
):
    try:
        suite_uuid = uuid.UUID(suite_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid suite UUID format")
        
    suite = db.query(models.TestSuite).filter(models.TestSuite.id == suite_uuid).first()
    if not suite:
        raise HTTPException(status_code=404, detail="TestSuite not found")
        
    # Enforce role verification
    check_user_role(db, user, str(suite.project_id), ["admin", "editor"])
    
    created_cases = []
    for c in payload.cases:
        case = models.TestCase(
            id=uuid.uuid4(),
            suite_id=suite_uuid,
            input_prompt=c.input_prompt,
            expected_output=c.expected_output,
            assertion_rules=c.assertion_rules
        )
        db.add(case)
        created_cases.append(case)
    db.commit()
    return {"message": f"Successfully uploaded {len(created_cases)} test cases"}

@app.post("/v1/runs", status_code=202)
def trigger_run(
    payload: RunCreate, 
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user)
):
    try:
        suite_uuid = uuid.UUID(payload.suite_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid suite UUID format")
        
    suite = db.query(models.TestSuite).filter(models.TestSuite.id == suite_uuid).first()
    if not suite:
        raise HTTPException(status_code=404, detail="TestSuite not found")
        
    # Enforce role verification
    check_user_role(db, user, str(suite.project_id), ["admin", "editor"])
    
    run = models.Run(
        id=uuid.uuid4(),
        suite_id=suite_uuid,
        model_name=payload.model_name,
        prompt_version=payload.prompt_version,
        status="PENDING"
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    
    # Trigger background Celery evaluation pipeline task
    from src.workers.celery_app import run_evaluation
    run_evaluation.delay(str(run.id))
    
    return {"run_id": str(run.id), "status": "PENDING"}

@app.get("/v1/runs/{run_id}")
def get_run_status(
    run_id: str, 
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user)
):
    try:
        run_uuid = uuid.UUID(run_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid run UUID format")
        
    run = db.query(models.Run).filter(models.Run.id == run_uuid).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
        
    # Enforce role verification
    check_user_role(db, user, str(run.suite.project_id), ["admin", "editor", "viewer"])
    
    results_count = len(run.results)
    avg_score = 0.0
    
    if run.status == "COMPLETED" and results_count > 0:
        total_scores = 0.0
        score_count = 0
        for result in run.results:
            for score_entry in result.scores:
                total_scores += score_entry.score
                score_count += 1
        avg_score = total_scores / score_count if score_count > 0 else 0.0

    return {
        "id": str(run.id),
        "suite_id": str(run.suite_id),
        "model_name": run.model_name,
        "prompt_version": run.prompt_version,
        "status": run.status,
        "created_at": run.created_at,
        "completed_at": run.completed_at,
        "results_count": results_count,
        "average_score": round(avg_score, 4)
    }

@app.get("/v1/runs/{run_id}/results")
def get_run_results(
    run_id: str, 
    db: Session = Depends(get_db),
    user: models.User = Depends(get_current_user)
):
    try:
        run_uuid = uuid.UUID(run_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid run UUID format")
        
    run = db.query(models.Run).filter(models.Run.id == run_uuid).first()
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")
        
    # Enforce role verification
    check_user_role(db, user, str(run.suite.project_id), ["admin", "editor", "viewer"])
        
    outcomes = []
    for res in run.results:
        scores = []
        for s in res.scores:
            scores.append({
                "metric_name": s.metric_name,
                "metric_type": s.metric_type,
                "score": s.score,
                "explanation": s.explanation
            })
        outcomes.append({
            "test_case_id": str(res.test_case_id),
            "input_prompt": res.test_case.input_prompt,
            "expected_output": res.test_case.expected_output,
            "actual_output": res.actual_output,
            "latency_ms": res.latency_ms,
            "prompt_tokens": res.prompt_tokens,
            "completion_tokens": res.completion_tokens,
            "total_tokens": res.total_tokens,
            "error_message": res.error_message,
            "scores": scores
        })
    return {"run_id": str(run.id), "results": outcomes}

@app.post("/v1/test-task")
def trigger_test_task(x: int, y: int):
    try:
        task = test_task.delay(x, y)
        return {"task_id": task.id, "status": "enqueued"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to queue task: {str(e)}")
