# Aegis: Self-Hosted LLM Evaluation & Observability Framework

Aegis is a self-hosted evaluation and observability framework designed to continuously test prompt quality, track regressions, and gate CI/CD pipelines, completely local and air-gapped.

---

## Genesis

* **Problem Observed**: Minor changes to prompts often silently regress model performance on edge cases, which usually goes undetected until customer complaints spike. Traditional validation requires hours of manual scratchpad comparisons per iteration.
* **SaaS Limitations**: Leading telemetry systems operate entirely as SaaS products. Due to strict corporate data compliance policies, sending proprietary prompts, system history datasets, and generated outputs to external third-party servers is prohibited.
* **Hypothesis**: By running an air-gapped evaluation framework locally behind a VPN, development teams can safely validate regressions in pipeline runs and block bad updates before they reach production.

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
│   ├── sdk-guide.md    # Documentation for Aegis SDK clients
│   └── evaluators-guide.md # Reference guide for rules, similarity, and LLM-as-judge scoring
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

## Advanced Evaluation Engine Features

Aegis implements specialized metrics to expand validation coverage:
* **Custom Metric Plugins**: Register custom Python scoring functions (inheriting from `BaseEvaluator`) in `src/plugins/` to implement custom checks (e.g. bias, containment, or formatting). Enabled via suite configurations.
* **Multi-Judge Consensus**: Configure multiple parallel LLM judges (e.g., GPT-4o and Llama-3.3) under `judge_config` to eliminate single-judge bias. The final score represents the mean score, with aggregated reasoning.
* **Local Toxicity Classifier**: A built-in plugin (`Toxicity Check`) using `unbiased-toxic-roberta` running locally inside the worker container to flag offensive outputs without sending data to third parties.
* **RAG Hallucination Grounding**: Dynamically triggered when test cases contain `context_documents` arrays, evaluating whether output sentences are semantically grounded in retrieved chunks using sentence-level cosine similarities.

See [evaluators-guide.md](file:///C:/Users/loyal/OneDrive/Desktop/Aegis/docs/evaluators-guide.md) for configurations and setup instructions.

---

## Observability Dashboard

Aegis includes a full-width real-time dashboard built with Streamlit and Plotly to monitor quality scores, track regression trends, and debug failed cases.
* **Access URL**: Open your browser and go to `http://localhost:8501`.
* **Observability Tabs**:
  - **Overview**: View metrics summary cards (run execution counts, average quality score, latency, and estimated token USD costs), version performance trendlines, registry lists, and case drill-downs.
  - **A/B Comparison**: Compares two prompt evaluation runs side-by-side to highlight output changes and delta scoring regressions.
  - **Regression Heatmap**: Plotly matrix heatmap visualizing quality transitions across the last 10 completed runs case-by-case.
  - **Alert Configs**: CRUD interface to register Slack, Discord, and webhook alert triggers with custom sliders for regression thresholds.
* **Formatted Markdown Rendering**: Model completions render using structured markdown parser for rich text (bolding, bullet points, headers) readability.
* **Color-Coded Status Badges**: Metrics evaluation scores flagged using clean green/orange/red badges (`PASS` / `WARN` / `FAIL`).

---

## CI/CD Regression Gating

Integrate prompt gating into code delivery pipelines using the python client runner script:
```bash
python CLI/runner.py \
  --suite_id "<SUITE_UUID>" \
  --model_name "llama-3.1-8b-instant" \
  --prompt_version "v1.1" \
  --threshold 0.85 \
  --api_url "http://localhost:8000"
```
The runner polls the Aegis server and returns exit code `0` on success or `1` if quality falls below the specified threshold, blocking the deployment.

See the Actions template in [.github/workflows/aegis-gate.yml](file:///C:/Users/loyal/OneDrive/Desktop/Aegis/.github/workflows/aegis-gate.yml).

---

## License
Open Source.
