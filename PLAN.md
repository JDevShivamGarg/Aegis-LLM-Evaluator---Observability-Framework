# Aegis: Self-Hosted LLM Evaluation & Observability Framework

**Tagline:** A self-hosted evaluation and observability framework to continuously test prompt quality, track regression, and gate CI/CD pipelines.  
**Category:** `ai-ml`  
**Author:** [@jdevshivamgarg](https://github.com/jdevshivamgarg)  
**Date:** 2026-07-01  
**Status:** `Complete`  

---

## 1. Genesis

**Problem observed:**  
During the deployment of an LLM-based customer support agent in production, a minor change to the system prompt designed to address customer refund queries silently regressed the model's accuracy on billing and account recovery requests. This quality degradation was only detected after customer complaints spiked, as testing required manually running prompts and checking outputs in developer scratchpads, taking 5 to 6 hours per prompt iteration.

**Why existing solutions fail:**  
Existing tools like LangSmith and Braintrust provide telemetry and evaluation suite features but operate entirely as SaaS products. Due to strict corporate data compliance policies, sending proprietary prompts, client history datasets, and generated outputs to external third-party servers is prohibited. Open-source command-line alternatives like Promptfoo exist but lack a persistent, multi-user dashboard to compare performance regressions, track latency across model versions, and offer robust, self-hosted team collaboration features.

**Core hypothesis:**  
If a self-hosted, air-gapped LLM evaluation and observability framework exists, then development teams can run continuous automated prompt and pipeline regressions safely behind their own VPNs, blocking poor-quality updates before they reach production.

---

## 2. Engineering Principles

1. **Air-gapped by Default** — The core service must never require an external network connection for scoring calculations. Embeddings similarity models and assertion rules must execute locally on containerized worker nodes.
2. **Deterministic Evaluation Gates** — Evaluation logic (regex, schema, semantic similarity) must return predictable, reproducible values. LLM-as-judge configurations must use strict schemas, zero-temperature parameters, and Chain-of-Thought (CoT) parsing to minimize run-to-run scoring variance.
3. **Out-of-Band Instrumentation** — Evaluation compute must never block or delay production application requests. High-throughput evaluation calculations are run as asynchronous worker tasks managed via a persistent queue.

---

## 3. Target Persona

**Who they are:**  
AI Engineers, LLM App Developers, and Backend Software Developers. They write prompt templates, build RAG pipelines (using LangChain or custom orchestrations), version model calls, and deploy these pipelines to customer-facing environments.

**How they currently solve this problem:**  
They maintain ad-hoc Python notebooks or run manual curl commands, comparing sample inputs and output responses by eye across a spreadsheet list of 20-30 test cases.

**What they will switch from and why:**  
They will switch from manual visual review workflows and commercial SaaS systems. The trigger is either a compliance security mandate banning the export of telemetry data to SaaS platforms, or a major production outage caused by an undetected prompt regression.

---

## 4. Problem Statement

Without a centralized, automated evaluation framework, developers cannot guarantee that LLM prompt updates or model migrations (e.g., migrating from GPT-4 to GPT-4o) do not introduce subtle quality regressions, new hallucinations, or compliance violations.
- **Cost of the problem:** Inaccurate responses in customer-facing production bots harm brand reputation, increase support triage overhead, and cost developers 10+ hours per week in manual verification scripts.
- **Underlying assumptions:** The developer already has a defined set of desired outputs or guidelines (gold dataset) and can allocate local CPU/GPU compute infrastructure to support continuous test execution.

---

## 5. Solution Overview

**What this system does:**  
Aegis is a self-hosted evaluation and regression testing platform. It manages projects, test suites, and test runs. It supports rule-based assertions (schema validation, regex, JSON output verification), local semantic embedding regressions, and LLM-as-judge scoring. Aegis features a CLI tool designed to trigger tests during GitHub Actions CI runs, an API Server to orchestrate execution, background worker nodes to handle non-blocking LLM/metric evaluation, and an interactive Streamlit/Plotly dashboard displaying project test history, model latency trends, and prompt regressions.

**Explicit non-goals (what this does NOT do):**  
- Does not: Act as a reverse proxy or gateway routing production traffic to LLM endpoints. Reason: Serving live traffic introduces strict runtime latency and SLA requirements. The system operates strictly as a development test/evaluation tool.
- Does not: Automatically re-engineer prompts. Reason: Prompt optimization depends highly on application context and remains a developer-driven task. Aegis provides evaluation and regression metrics rather than generative prompts.
- Does not: Fine-tune custom LLM models. Reason: Aegis is designed for testing and quality assurance rather than training model weights.

---

## 6. System Architecture

```mermaid
graph TD
    A[GitHub Actions / Local CLI] -->|HTTPS| B[FastAPI API Server]
    C[Streamlit Dashboard] -->|SQL Query| D[(PostgreSQL)]
    B -->|Write Run / Fetch| D
    B -->|Enqueue Run Task| E[(Redis Queue)]
    F[Celery Background Worker] -->|Dequeue Task| E
    F -->|Call APIs| G[Target LLM Provider]
    F -->|Local Cosine Sim / Scoring| H[Local Sentence-Transformers Embedding Model]
    F -->|Write Results| D
```

**Component breakdown:**

| Component | Responsibility | Communicates With |
|---|---|---|
| FastAPI API Server | Exposes endpoints to trigger runs, manage suites, retrieve run statuses, and serve data models. | PostgreSQL, Redis Queue |
| Celery Background Worker | Dequeues evaluation tasks, makes target model calls, runs embedding models, performs rule validations, and stores logs. | Redis Queue, PostgreSQL, Target LLM, Sentence-Transformers |
| Redis Queue | Serves as the message broker for background task scheduling. | FastAPI API Server, Celery Background Worker |
| PostgreSQL | Stores projects, test suites, test cases, evaluation run configurations, metrics, logs, and score outcomes. | FastAPI API Server, Celery Background Worker, Streamlit Dashboard |
| Streamlit Dashboard | Visualizes evaluation trends, latency stats, prompt regressions, and failure breakdowns. | PostgreSQL |
| CLI Runner | Triggers runs in CI/CD, polls API server for completion, and returns an exit code based on evaluation success thresholds. | FastAPI API Server |

**Non-negotiable constraints:**  
- Local metric isolation: Semantic and rule assertions must process on local container hardware. Local similarity evaluation tasks must run without sending payload variables to third-party endpoints.
- Out-of-band execution: All test evaluations must run asynchronously. Handlers within the API Server must limit tasks to queue insertion rather than running metrics calculations inline.
- Strict schema validation: All database insertions for raw logs, inputs, and configurations must be validated using Pydantic templates.

---

## 7. Data Flow

```mermaid
sequenceDiagram
    participant CI as GitHub Actions CLI
    participant API as FastAPI API Server
    participant DB as PostgreSQL
    participant Q as Redis Queue
    participant W as Celery Background Worker
    participant LLM as Target LLM Provider

    CI->>API: POST /v1/runs {project_id, suite_id, target_model, prompt_version}
    API->>DB: INSERT INTO runs (status = 'PENDING')
    API->>Q: LPUSH celery_queue (run_id)
    API-->>CI: 202 Accepted {run_id}
    
    W->>Q: RPOP celery_queue
    W->>DB: Fetch test cases for suite_id
    loop For each test case
        W->>LLM: Generate output (input_prompt)
        LLM-->>W: Return actual_output, token_counts, latency
        W->>W: Execute Local Assertions (Regex, JSON)
        W->>W: Run local Sentence-Transformers Cosine Similarity
        W->>W: Run LLM-As-Judge Scoring (if configured)
        W->>DB: INSERT INTO test_results & metric_scores
    end
    W->>DB: UPDATE runs (status = 'COMPLETED')
    
    loop Every 2 seconds (polling)
        CI->>API: GET /v1/runs/{run_id}
        API->>DB: SELECT status, scores
        DB-->>API: run_status = 'COMPLETED'
        API-->>CI: 200 OK {success: true, passed: true, score: 0.92}
    end
    CI-->>CI: Exit code 0 (threshold passed)
```

---

## 8. Data Models

**Core entities and relationships:**

```mermaid
erDiagram
    PROJECT ||--o{ TEST_SUITE : contains
    TEST_SUITE ||--o{ TEST_CASE : defines
    TEST_SUITE ||--o{ RUN : executes
    RUN ||--o{ TEST_RESULT : produces
    TEST_CASE ||--o{ TEST_RESULT : evaluates
    TEST_RESULT ||--o{ METRIC_SCORE : records
```

**Schema decisions:**

| Decision | Reason |
|---|---|
| UUID Primary Keys | Prevents enumeration exposure and simplifies decoupled client-side ID generation. |
| JSONB for assertions configuration | Assertion requirements change from case to case (some require JSON, others regex). JSONB provides schema-less rule customization. |
| Denormalized tokens and latency metrics | Simplifies visualization engine queries in Streamlit without running complex, slow aggregate joins on log tables. |

**Schema definition (runnable DDL):**

```sql
CREATE TABLE projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE test_suites (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id UUID NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE test_cases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    suite_id UUID NOT NULL REFERENCES test_suites(id) ON DELETE CASCADE,
    input_prompt TEXT NOT NULL,
    expected_output TEXT,
    assertion_rules JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    suite_id UUID NOT NULL REFERENCES test_suites(id) ON DELETE CASCADE,
    model_name VARCHAR(100) NOT NULL,
    prompt_version VARCHAR(50) NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'PENDING',
    triggered_by VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

CREATE TABLE test_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id UUID NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    test_case_id UUID NOT NULL REFERENCES test_cases(id) ON DELETE CASCADE,
    actual_output TEXT,
    latency_ms INT,
    prompt_tokens INT,
    completion_tokens INT,
    total_tokens INT,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE metric_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    test_result_id UUID NOT NULL REFERENCES test_results(id) ON DELETE CASCADE,
    metric_name VARCHAR(100) NOT NULL,
    metric_type VARCHAR(50) NOT NULL, -- 'LLM_JUDGE', 'EMBEDDING_SIMILARITY', 'RULE_ASSERTION'
    score DOUBLE PRECISION NOT NULL,
    explanation TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_runs_suite ON runs(suite_id);
CREATE INDEX idx_test_results_run ON test_results(run_id);
CREATE INDEX idx_metric_scores_result ON metric_scores(test_result_id);
```

---

## 9. Tech Stack

| Layer | Choice | Reason | Rejected Alternative | Why Rejected |
|---|---|---|---|---|
| Language | Python 3.11 | Extensive library ecosystem for ML modeling (PyTorch, transformers) and LangChain eval compatibility. | Go | Lacks native support for HuggingFace model configurations, forcing an external microservice for local similarity calculations. |
| Framework | FastAPI | Low-overhead asynchronous endpoints, strict validation with Pydantic, and fast integration testing. | Flask | Lacks out-of-the-box async features and requires manual packages for payload validation. |
| Database (primary) | PostgreSQL 15 | Robust aggregate analytical indexes and fast JSONB structure execution for arbitrary testing assertions. | MongoDB | Complex schema analytics and metrics history aggregation perform poorly on document architectures without joins. |
| Cache & Broker | Redis 7 | Lightweight message broker with sub-millisecond persistence and fast list manipulation. | RabbitMQ | Lacks storage utility; using Redis allows it to act as both a message broker and cache storage. |
| Task Runner | Celery 5.3 | Industry standard Python framework with native task queuing, exponential retries, and failure handlers. | Custom python thread pools | Requires extensive customization to support persistent runs, cluster deployment, and worker failures. |
| Auth | Custom OAuth2 JWT | Simplifies packaging and dependencies for local Docker installations. | Clerk / Auth0 | Requires third-party web connection; fails the core principle of a fully self-contained air-gapped system. |
| File storage | Local Docker volumes | Small textual evaluation outputs scale nicely inside DB storage or flat container files. | AWS S3 | Adds configuration complexity and requires cloud access for basic local installations. |
| Hosting | Docker Compose / k8s | Platform-agnostic container templates easily run on localized virtualization hardware. | AWS ECS | Couples the deployment to proprietary cloud hosting platforms, preventing on-premises deployments. |
| CI/CD | GitHub Actions | Native market runners simplify step integrations directly in modern repositories. | Jenkins | Higher configuration complexity and server administration overhead. |
| Monitoring | Prometheus & Grafana | Open-source, easily dockerized metrics exporter matching self-hosted profiles. | Datadog | Expensive software tool that ships internal project metrics to cloud locations. |

**Key dependencies (concrete package list):**

| Package | Purpose |
|---|---|
| `fastapi` | REST API framework for runs and data ingestion. |
| `celery` | Task orchestration for evaluation queue pipelines. |
| `psycopg2-binary` | Driver to connect FastAPI/Celery to PostgreSQL. |
| `sentence-transformers` | Executes local embeddings (e.g. `all-MiniLM-L6-v2`) for regression verification without API traffic. |
| `openai` | Client backend for OpenAI model evaluation runs. |
| `pydantic` | Runs strict schema validation on inputs and runs data shapes. |
| `streamlit` | Renders the dashboard and statistics panels. |
| `plotly` | Renders regression plots and latency timelines. |

---

## 10. Project Structure

```
llm-eval-observability-framework/
├── src/
│   ├── api/            # API endpoints (projects, runs, suites)
│   ├── core/           # Database configurations and app settings
│   ├── services/       # Assertion checkers (LLMJudge, EmbeddingSim, RuleAssert)
│   ├── repositories/   # Direct SQL and data models query mappings
│   ├── workers/        # Celery application setups and runner handlers
│   └── dashboard/      # Streamlit dashboard script files
├── tests/
│   ├── unit/           # Unit tests for rule parsing and scoring calculations
│   ├── integration/    # Database writing and queue workflow validations
│   └── e2e/            # Complete runner to API pipeline validation checks
├── CLI/                # Package code for local CLI executor
├── infra/              # Dockerfiles, configs, docker-compose.yml
├── .env.example        # Configuration template
├── requirements.txt    # Application dependencies
└── README.md           # Getting started instructions
```

**Structural decisions:**

| Decision | Reason |
|---|---|
| Separation of `services/` | Evaluator engines must not import FastAPI frameworks, ensuring clean execution in tests and terminal sessions. |
| Decoupled `repositories/` | Database transaction code remains separated from endpoints, simplifying schema upgrades and caching implementation. |
| Standalone `CLI/` | Keeps runner executables clean and dependencies minimal when imported into simple runner environments. |

---

## 11. Configuration Reference

```bash
# === Service Databases ===
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/eval_db
REDIS_URL=redis://localhost:6379/0

# === Authentication Keys ===
JWT_SECRET=aegis_local_dev_secret_key_change_in_production
JWT_EXPIRY_SECONDS=3600

# === Worker Parameters ===
CELERY_CONCURRENCY=4
EMBEDDING_MODEL_PATH=all-MiniLM-L6-v2
EVAL_MAX_RETRIES=3
EVAL_TIMEOUT_SECONDS=30

# === LLM Provider Configuration ===
OPENAI_API_KEY=sk-placeholder
```

| Variable | Default | Controls | Why This Default |
|---|---|---|---|
| `DATABASE_URL` | `postgresql://postgres:postgres@localhost:5432/eval_db` | Connection target for the PG server. | Standard developer image endpoint structure. |
| `REDIS_URL` | `redis://localhost:6379/0` | Target redis cache and task broker connection. | Standard developer image endpoint structure. |
| `JWT_SECRET` | `aegis_local_dev_secret_key_change_in_production` | Key used to sign authorization tokens. | Developer convenience; must change in production deployments. |
| `JWT_EXPIRY_SECONDS` | `3600` | Expiration lifespan for JWT auth tokens. | Balance between security scope and local developer convenience. |
| `CELERY_CONCURRENCY` | `4` | Worker process counts per instance. | Prevent CPU bottlenecks on standard dual-core development machines. |
| `EMBEDDING_MODEL_PATH` | `all-MiniLM-L6-v2` | Model loaded by Sentence-Transformers. | Highly performant model that runs efficiently on simple CPUs. |
| `EVAL_MAX_RETRIES` | `3` | Attempts to query remote target LLM models on timeout/error. | Safe buffer against transient network connection issues. |
| `EVAL_TIMEOUT_SECONDS` | `30` | Network request cut-off timeout. | Prevents pipeline hanging on slow API server completions. |
| `OPENAI_API_KEY` | `sk-placeholder` | OpenAI token configuration. | Placeholder to prevent validation issues on service initialization. |

---

## 12. API Design

**Authentication strategy:** Custom JWT (JSON Web Tokens) for dashboard and API endpoints; permanent API keys generated via database mapping for CI/CD runners. Reason: Keeps the security flow entirely local and self-hosted.

**Versioning strategy:** URI versioning `/v1/` for clean routing. Reason: Prevents breaking changes in runner scripts when updating payload schemas.

**Core endpoints:**

| Method | Endpoint | Auth Required | Description | Rate Limit |
|---|---|---|---|---|
| POST | `/v1/projects` | Yes | Create project | 10/min per IP |
| POST | `/v1/projects/:id/suites` | Yes | Create test suite | 30/min per user |
| POST | `/v1/suites/:id/cases` | Yes | Batch upload test cases | 30/min per user |
| POST | `/v1/runs` | Yes | Trigger evaluation run | 20/min per user |
| GET | `/v1/runs/:id` | Yes | Get run status and overall scores | 120/min per user |
| GET | `/v1/runs/:id/results` | Yes | Get detailed test cases results | 60/min per user |

**Error response shape:**
```json
{
  "error": {
    "code": "VALIDATION_FAILED",
    "message": "The evaluation run configuration has invalid assertion rules.",
    "field": "assertion_rules"
  }
}
```

**Pagination shape:**
```json
{
  "data": [],
  "pagination": {
    "cursor": "MjAyNi0wNy0wMVQwODo1NTozOQ==",
    "has_next": true,
    "limit": 20
  }
}
```

**Internal service contracts:**

```python
# FastAPI to Celery Queue — Task Input Schema
class EvaluationTaskPayload(BaseModel):
    run_id: str
    test_case_ids: list[str]
    target_model_config: dict  # contains provider, model_name, api_base, temp

# Celery Worker to Database — Task Complete Schema
class EvaluationTaskResult(BaseModel):
    run_id: str
    test_case_id: str
    status: str  # 'SUCCESS' | 'FAILED'
    actual_output: str | None
    latency_ms: int
    prompt_tokens: int
    completion_tokens: int
    scores: list[dict]  # contains: metric_name, metric_type, score, explanation
    error_message: str | None
```

---

## 13. Security

**Threat model:**

| Threat | Vector | Mitigation |
|---|---|---|
| Sensitive Data Leakage | Prompts shipped to SaaS providers | Ensure core engine runs on-premise; local embeddings calculations. |
| API Key Exposure | Remote key stored inside target database | Remote key configurations are stored in environment memory; never stored in the database. |
| Prompt Injection | Malicious payload in test response hijacks LLM Judge | Format LLM Judge system prompts using strict delimiter validation XML wrappers and JSON output constraints. |
| Access Abuse | External user triggers bulk runs | Authentication verification is required on all endpoints; API endpoints enforce rate-limiting. |
| DoS on internal network | Massive batch runs overload API DB resources | Rate limits enforce maximum case batch inputs and set Celery queue limits. |

**Auth/AuthZ decisions:**
- Token type: HMAC-SHA256 JWT for dashboard access; SHA256 hashed API Keys for runners.
- Token expiry: Dashboard JWT: 12 hours. Reason: Prevents long-lived session exploits, suitable for internal developer tools.
- Refresh strategy: Absolute. Reason: Minimal session complexity for internal usage.
- Permission model: Project-level RBAC (Reader, Editor, Admin). Reason: Ensures teams can separate evaluations for different models.

**Sensitive data handling:**
- Passwords: PBKDF2 with SHA256 (Django default) or bcrypt with cost factor 12.
- PII fields: Optionally masked in test cases and results using a basic regex scrubber pre-persistence.
- Logging: Environment variables and keys are redacted from logs automatically using a custom log filter.
- Data at rest: PostgreSQL volumes encrypted using dm-crypt/LUKS at the hosting OS level.
- Data in transit: TLS 1.3 forced on API endpoints and Streamlit dashboard reverse proxy.

**Blast radius of a breach:**
- (a) Database compromise: Attacker gains all historical prompts, test cases, model outputs, latency metrics, and API keys hashes (no raw external LLM keys since they aren't stored in DB).
- (b) API Server compromise: Attacker gains memory access containing transient raw external LLM keys (OPENAI_API_KEY etc.), can trigger unauthorized evaluation runs.
- (c) User's session token compromise: Attacker can view/modify projects, test suites, and read run history for the duration of the 12h session.

---

## 14. Scalability

**Current design ceiling:**  
The architecture supports approximately 100 concurrent evaluation runs (averaging 50 test cases per run) or 150 LLM API requests per second before the PostgreSQL database write connection pool or worker memory becomes the bottleneck.

**First bottleneck:**  
Database Connection Pool Starvation — Celery workers write run metrics and test case logs concurrently. Under heavy run volumes, workers will exhaust available database connection slots, resulting in timeout writing failures.

**Scaling path:**

| Stage | Users | Change Required |
|---|---|---|
| MVP | 0–1K | Single Docker Compose environment running on a single cloud server instance. |
| Growth | 1K–50K | Deploy components to Kubernetes; migrate PG and Redis to managed services; autoscale workers. |
| Scale | 50K–500K | Deploy PgBouncer connection pool; partition PG tables (`test_results` and `metric_scores`) by `run_id`. |
| Beyond | 500K+ | Migrate analytics telemetry storage to an OLAP database like ClickHouse to prevent blocking dashboard queries. |

**Caching strategy:**

| What is cached | Where | TTL | Invalidation trigger |
|---|---|---|---|
| Project metadata | Redis | 1 Hour | Project modification endpoint trigger. |
| Aggregated statistics dashboard stats | Redis | 5 Minutes | Run completed update trigger. |

---

## 15. Testing Strategy

| Level | Tool | What It Tests | When It Runs |
|---|---|---|---|
| Unit | PyTest | Evaluators, score equations, regression validations, formatting. | Every commit on any branch |
| Integration | PyTest + TestContainers | DB query implementations, repository functions, worker queues. | Every PR to main |
| Contract | PyTest + Schemathesis | FastAPI responses strictly conform to Pydantic definitions. | Every PR to main |
| End-to-end | Shell/Python scripts | Runner CLI executes complete run, queries API, checks output exit code. | Nightly |
| Security | Bandit / Safety | Static code analysis and third-party library vulnerabilities. | Every PR to main |
| Load | Locust | Concurrent API endpoints capacity for job execution. | Pre-release / Manual |

---

## 16. Build vs Buy

| Component | Decision | Reason |
|---|---|---|
| Database | Buy (Managed PG Cloud Services) | High operational overhead to manage backups, recovery, and disk upgrades. |
| Queue Broker | Build (Self-hosted Redis container) | Simple configuration pipeline; container maintenance represents minimal developer work. |
| Evaluator Engine | Build | Core differentiator. Tailored custom evaluation assertions and local semantic models. |
| Identity Provider | Build (Local simple JWT login) | Third-party services require network egress. A simple secure database-backed login keeps the deployment air-gapped. |

---

## 17. Key Algorithms & Critical Logic

### Cosine Similarity & LLM Judge Score Extraction
**Why this needs a reference implementation:**  
Poor implementation of local embedding similarities yields numeric bugs. LLM-as-Judge outputs often fail to conform to simple integer formatting rules if they output conversational prefixes.

```python
import re
import numpy as np

class EmbeddingSimilarityEvaluator:
    """Calculates cosine similarity between expected and actual outputs using local embeddings."""
    def __init__(self, model):
        # model is a sentence-transformers instance loaded locally
        self.model = model

    def score(self, expected: str, actual: str) -> float:
        if not expected or not actual:
            return 0.0
        # Encode sentences to get their embedding vectors
        embeddings = self.model.encode([expected, actual])
        v1, v2 = embeddings[0], embeddings[1]
        
        # Calculate cosine similarity
        dot_product = np.dot(v1, v2)
        norm_v1 = np.linalg.norm(v1)
        norm_v2 = np.linalg.norm(v2)
        
        if norm_v1 == 0 or norm_v2 == 0:
            return 0.0
            
        similarity = dot_product / (norm_v1 * norm_v2)
        # Clip to [0, 1] range to avoid floating point anomalies
        return float(np.clip(similarity, 0.0, 1.0))

class LLMAsJudgeParser:
    """Extracts a numeric score and explanation from a structured LLM response."""
    @staticmethod
    def parse_judge_response(response_text: str) -> tuple[float, str]:
        # Expecting XML tags: <explanation>...</explanation> and <score>X</score>
        score_match = re.search(r"<score>\s*([0-9.]+)\s*</score>", response_text, re.IGNORECASE)
        explanation_match = re.search(r"<explanation>(.*?)</explanation>", response_text, re.IGNORECASE | re.DOTALL)
        
        score = 0.0
        explanation = "Failed to parse explanation."
        
        if score_match:
            try:
                score = float(score_match.group(1))
            except ValueError:
                pass
                
        if explanation_match:
            explanation = explanation_match.group(1).strip()
        else:
            # Fallback: clean raw text
            explanation = re.sub(r"<score>.*?</score>", "", response_text, flags=re.IGNORECASE | re.DOTALL).strip()
            
        return score, explanation
```

---

## 18. Failure Modes

| Component | Failure Scenario | Degradation Strategy |
|---|---|---|
| Target LLM API | Rate limit exceeded / Timeout | Retry using exponential backoff up to 3 times; if failure persists, mark result as FAILED with error context, letting other results continue. |
| Redis Broker | Redis crash / Unavailable | API logs failure and returns 503 Service Unavailable to new run requests. Celery workers poll Redis connection until re-established. No data loss for completed DB records. |
| PostgreSQL DB | Write limits / Pool exhausted | Queue worker writes fail. Workers use Celery's built-in retry mechanism to re-queue the result write-back tasks with backoff. |
| Local Embedding Model | Out Of Memory (OOM) on host | Celery task fails. Task is re-queued with reduced batch size or falls back to CPU-only execution path. |
| CI/CD Runner | Network cutoff during poll | Runner exits with code 2 (unknown status) to avoid silently deploying failing prompts, requiring manual verification. |

---

## 19. Risk Register

**Distinct from Failure Modes.**

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| CPU execution of local sentence embeddings is too slow for large batch sizes. | Medium | High | Support fallbacks to API-based embeddings (e.g. OpenAI embeddings) if local CPU latency exceeds 500ms per test case. |
| LLM Judge models produce non-deterministic score assessments. | High | Medium | Implement multi-judge consensus averaging and enable human-in-the-loop audit logs inside the dashboard to calibrate automated judge ratings. |
| Users fail to maintain high-quality gold test suite datasets. | High | High | Build a production logs importer that samples unique real-world conversations using clustering (e.g. TF-IDF/K-Means) to seed test cases. |

---

## 20. Cost Architecture

**All figures are rough order-of-magnitude estimates.**

| Resource | 100 runs/mo | 10K runs/mo | 100K runs/mo |
|---|---|---|---|
| Compute | $10 | $40 | $200 |
| Database | $15 | $50 | $200 |
| Cache & Broker | $0 (local) | $15 | $60 |
| Storage | $2 | $10 | $50 |
| LLM API Calls | $5 | $300 | $2,500 |
| **Total estimate** | **$32** | **$415** | **$3,010** |

**Cost ceiling:**  
At 500K runs/mo, LLM API costs (specifically OpenAI GPT-4 judge calls) will dominate. The unit economics remain viable because testing code reliability in development prevents major customer support cost spikes, but teams can optimize by swapping the judge model to a fine-tuned local Llama-3-8B running on a dedicated low-cost GPU instance.

---

## 21. Limitations

- **Rate Limit Constrained Evaluations:** The framework's throughput is strictly bounded by the target LLM provider's rate limits (TPM/RPM). If running a 1,000 test case suite against a tier-1 OpenAI model, the execution time will be dominated by rate limit retry delays (often taking up to 10-15 minutes).
- **GPU Resource Contention:** If running sentence-similarity evaluations locally on a CPU without a GPU, throughput is limited. High concurrency runs can cause high CPU utilization, slowing down HTTP API response times if hosted on the same instance.
- **Judge Model Dependency:** LLM-as-judge scores are highly sensitive to prompt template updates. Modifying the judge system prompt will break historical metrics compatibility, rendering older scores incomparable to new runs.

---

## 22. Rejected Alternatives

| Alternative | Why Considered | Why Rejected |
|---|---|---|
| LangSmith / Braintrust | Turnkey solutions, ready-made visualization, robust dataset versioning | Violated security and compliance policies requiring 100% on-premises/air-gapped data retention. Data containing customer PII cannot be shipped to external SaaS endpoints. |
| CLI-only runner (e.g. Promptfoo) | Extremely simple setup, low resource overhead, runs locally | Lacked persistent history, multi-user visual dashboard for prompt regression, and historical telemetry correlation across model versions. |
| Ragas (alone) | Popular library containing ready-made RAG metric evaluators | Ragas is a library, not a system. It lacks a task runner, API endpoints, web dashboard, and CI integration required for continuous integration pipeline gating. |

---

## 23. Decision Log

| # | Decision | Options Considered | Chosen | Reason | Trade-off Accepted |
|---|---|---|---|---|---|
| 1 | Python & FastAPI | Go, Node.js | Python & FastAPI | Simple integration with HuggingFace and evaluation tools. | Marginally lower HTTP request handling scale compared to Go. |
| 2 | PostgreSQL for storage | MongoDB, ClickHouse | PostgreSQL | Relational constraints are ideal for projects, runs, and suites. | Lower performance scaling with logs, requiring partitioning later. |
| 3 | Streamlit for dashboard | React / Next.js | Streamlit | Rapid development for AI telemetry representation. | Less UI customizability and rendering latency under load. |
| 4 | Celery for workers | Custom thread pool, Arq | Celery | Robust task retries and error routing mechanisms. | Heavy dependencies and complex setup configurations. |

---

## 24. Implementation Roadmap

**Phase 1 — Core API & Storage (Week 1–2)**
- [ ] Initialize Python FastAPI repository and docker configuration setups.
- [ ] Setup PostgreSQL schemas and write DB connection pools.
- [ ] Integrate Redis task queues and celery worker run modules.

**Phase 2 — Evaluation Engine & Workers (Week 3–4)**
- [ ] Write worker handlers for LLM-as-judge, local embedding similarity, and rule parsing.
- [ ] Build execution workflows for polling test run states.
- [ ] Implement database write-back pipelines for scoring outputs.

**Phase 3 — Dashboard & CLI CI Integration (Week 5–6)**
- [ ] Build the Streamlit dashboard layout displaying historical charts.
- [ ] Develop the python client CLI runner for CI terminal execution.
- [ ] Implement GitHub Actions workflow gating and complete end-to-end integration tests.

---

## 25. Future Work

**Phase 1 — Production Shadow Evaluations**  
Trigger: When production query volume using target LLMs exceeds 10,000 requests per day.  
- [ ] Deploy log streaming middleware to queue live traffic samples into evaluation test suites.
- [ ] Build automated clustering tools to detect out-of-distribution queries.

**Phase 2 — Local Fine-Tuned Judge Model**  
Trigger: When external LLM-as-judge API billing costs exceed $1,000/mo.  
- [ ] Train a local 8B parameter model (e.g. Llama-3-8B-Instruct) on historical GPT-4 judge score outputs.
- [ ] Deploy the local judge container on worker clusters.

---

## 26. References

- [LangChain Evaluators](https://python.langchain.com/docs/guides/evaluation/) — Influenced: Architecture of the evaluator module and metric types.
- [Promptfoo GitHub](https://github.com/promptfoo/promptfoo) — Influenced: CLI configuration design and assertion rule structure.
- [Sentence-Transformers (HuggingFace)](https://huggingface.co/sentence-transformers) — Influenced: Choice of local models for embedding similarity regression.
