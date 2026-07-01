from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from src.core.database import get_db
from src.workers.celery_app import test_task

app = FastAPI(
    title="Aegis API Server",
    description="Self-Hosted LLM Evaluation & Observability Framework API",
    version="1.0.0"
)

@app.get("/")
def read_root():
    return {"message": "Welcome to Aegis LLM Evaluation Server"}

@app.get("/health")
def health_check(db: Session = Depends(get_db)):
    try:
        db.execute("SELECT 1")
        db_status = "healthy"
    except Exception as e:
        db_status = f"unhealthy: {str(e)}"
    
    return {
        "status": "healthy",
        "database": db_status
    }

@app.post("/v1/test-task")
def trigger_test_task(x: int, y: int):
    try:
        task = test_task.delay(x, y)
        return {"task_id": task.id, "status": "enqueued"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to queue task: {str(e)}")
