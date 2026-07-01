# Aegis: Self-Hosted LLM Evaluation & Observability Framework

Aegis is a self-hosted evaluation and observability framework designed to continuously test prompt quality, track regressions, and gate CI/CD pipelines, completely local and air-gapped.

---

## Repository Structure

```text
Aegis/
├── src/
│   ├── api/            # API server endpoints (FastAPI)
│   ├── core/           # Database pools and global settings configurations
│   ├── services/       # Assertion logic, scoring, and embeddings evaluators (Phase 2)
│   ├── repositories/   # Database query definitions and mappings
│   ├── workers/        # Celery background workers and runners
│   └── dashboard/      # Interactive Streamlit dashboards (Phase 3)
├── infra/
│   ├── Dockerfile.api  # Build config for the FastAPI container
│   ├── Dockerfile.worker # Build config for the Celery worker container
│   ├── init.sql        # Database initialization schema scripts
│   └── docker-compose.yml # Docker Compose services coordinator
├── .env.example        # Environment variable configuration template
├── requirements.txt    # Python package dependencies list
└── README.md           # Getting started manual
```

---

## Local Setup

### Prerequisites
- Docker & Docker Compose installed.

### Setup Instructions
1. **Configure Environment Variables**:
   Copy the example environment file and configure your keys:
   ```bash
   cp .env.example .env
   ```
   Open the `.env` file and insert your `OPENAI_API_KEY` and/or `GROQ_API_KEY`.

2. **Run with Docker Compose**:
   To build and start all containers (API Server, Celery Worker, PostgreSQL database, and Redis broker) in the background, run:
   ```bash
   docker compose -f infra/docker-compose.yml up --build -d
   ```

3. **Verify Health**:
   Query the API server's health status check:
   ```bash
   curl http://localhost:8000/health
   ```
   The database status should return `"healthy"`.

4. **Trigger a Test Task**:
   Enqueue a background Celery task via the API endpoint:
   ```bash
   curl -X POST "http://localhost:8000/v1/test-task?x=10&y=20"
   ```

---

## License
Open Source.
