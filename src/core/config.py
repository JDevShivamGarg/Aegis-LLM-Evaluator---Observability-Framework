from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/eval_db"
    REDIS_URL: str = "redis://localhost:6379/0"
    JWT_SECRET: str = "aegis_local_dev_secret_key_change_in_production"
    JWT_EXPIRY_SECONDS: int = 3600
    CELERY_CONCURRENCY: int = 4
    EMBEDDING_MODEL_PATH: str = "all-MiniLM-L6-v2"
    EVAL_MAX_RETRIES: int = 3
    EVAL_TIMEOUT_SECONDS: int = 30
    OPENAI_API_KEY: str = "sk-placeholder"
    GROQ_API_KEY: str = "gsk-placeholder"

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
