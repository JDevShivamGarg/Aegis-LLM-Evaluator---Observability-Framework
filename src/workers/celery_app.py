from celery import Celery
from src.core.config import settings

celery = Celery(
    "aegis_tasks",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL
)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    worker_concurrency=settings.CELERY_CONCURRENCY,
)

# A placeholder task to verify worker execution
@celery.task(name="src.workers.celery_app.test_task")
def test_task(x: int, y: int) -> int:
    return x + y
