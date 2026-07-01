# Aegis: Self-Hosted LLM Evaluation & Observability Framework

Aegis is a self-hosted evaluation and observability framework designed to continuously test prompt quality, track regressions, and gate CI/CD pipelines, completely local and air-gapped.

---

## Repository Structure

```text
Aegis/
├── src/
│   ├── api/            # API server endpoints (FastAPI)
│   ├── core/           # Database pools, ORM models, and global config
│   ├── services/       # Rule assertions, sentence embeddings, and LLM-as-judge (Phase 2)
│   ├── repositories/   # Database query definitions and mappings
│   ├── workers/        # Celery background workers and task runners
│   ├── sdk/            # Aegis Python SDK for inline evaluation and logging
│   ├── seed.py         # Database seeder script for real-world test suites
│   ├── agent_demo.py   # Agentic workflow SDK integration demo
│   └── dashboard/      # Interactive Streamlit dashboards (Phase 3)
├── docs/
│   ├── architecture.md # Architectural design patterns and data flows
│   └── sdk-guide.md    # Documentation for Aegis SDK clients
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
   docker compose -f infra/docker-compose.yml --env-file .env up --build -d
   ```

3. **Verify Health**:
   Query the API server's health status check:
   ```bash
   curl http://127.0.0.1:8000/health
   ```
   The database status should return `"healthy"`.

4. **Seed Database with Real-World Test Suites**:
   Run the idempotent database seeder to register RAG, PII, JSON Schema, and Compliance (Financial, Health, Legal) cases:
   ```bash
   docker exec aegis_api python -m src.seed
   ```

5. **Run Agentic Workflow Demo**:
   Verify the Aegis Python SDK (local in-memory evaluator and remote telemetry logging) by executing the mock customer support routing agent demo:
   ```bash
   docker exec aegis_api python -m src.agent_demo
   ```

---

## Aegis Python SDK

Exposes two developer interfaces for single-agent and multi-agent loops:
* **`AegisLocalEvaluator`**: Runs rule checks, regex matching, JSON schema verification, and Sentence-Transformer embedding similarities synchronously in-memory (no database required).
* **`AegisAPIClient`**: Exposes HTTP wrappers to log project runs and telemetry to the Aegis central database.

See [sdk-guide.md](file:///C:/Users/loyal/OneDrive/Desktop/Aegis/docs/sdk-guide.md) for complete code examples.

---

## License
Open Source.
