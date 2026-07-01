# Aegis Architecture Documentation

This document describes the architectural layout, component roles, and data flow of the Aegis LLM Evaluation and Observability Framework.

## 1. High-Level Design

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

## 2. Component Designations

* **FastAPI Server**: Front desk HTTP server exposing REST API endpoints to trigger test runs, manage suites, retrieve run statuses, and query logs.
* **Celery Worker**: Background task executor that processes run tasks, makes external LLM calls (via OpenAI or Groq), performs local evaluations (embeddings, schema assertions), and writes scoring metrics.
* **Redis**: Acts as the Celery task message broker and transient results backend cache.
* **PostgreSQL**: Serves as the persistent database engine storing configurations, projects, test cases, runs, and final metric scores.

## 3. Core Database Tables

The PostgreSQL database maintains the following entities (initialized via [init.sql](file:///C:/Users/loyal/OneDrive/Desktop/Aegis/infra/init.sql)):

* **`projects`**: Top-level namespace grouping test suites.
* **`test_suites`**: Logical groupings of related test cases.
* **`test_cases`**: Test specifications holding prompts, expected outputs, and assertion rules.
* **`runs`**: Execution entries documenting model names, status, and completion times.
* **`test_results`**: Output details per test case containing token counts, latency, and actual text outputs.
* **`metric_scores`**: Calculated metrics (e.g., cosine similarity, LLM-as-judge score) per test case result.

---

## 4. Client SDK Workflow Pathways

Aegis supports two distinct integration pipelines for single/multi-agent loops and tool pipelines:

### Pathway A: Local In-Memory Evaluator (`AegisLocalEvaluator`)
Used inside active agent execution loops to evaluate outputs synchronously before returning results to client requests (no DB or Celery connection required).

```mermaid
graph LR
    Agent[Agent execution loop] -->|1. check_rule| Rules[rules.py Assertions]
    Agent -->|2. check_similarity| Sim[similarity.py Local Embeddings]
    Agent -->|3. check_llm_judge| Judge[judge.py Groq/OpenAI Judge]
    Rules -->|Score & Explanation| Agent
    Sim -->|Cosine Similarity| Agent
    Judge -->|Structured Score| Agent
```

### Pathway B: Remote API Telemetry Client (`AegisAPIClient`)
Used to register sessions, runs, and case execution details into the persistent PostgreSQL database for historical analytics and regression dashboard visualization.

```mermaid
sequenceDiagram
    participant Agent as Routing Agent / Pipeline
    participant SDK as Aegis API Client
    participant API as Aegis API Server
    participant DB as PostgreSQL

    Agent->>SDK: 1. Session start: log_run(suite_id, model, version)
    SDK->>API: POST /v1/runs
    API->>DB: INSERT run status (PENDING)
    API-->>SDK: Return run_id
    SDK-->>Agent: Return run_id
    
    Agent->>Agent: Execute agent logic & tool calls
    
    Agent->>SDK: 2. Session completed: log_results(run_id, actual_outputs, metrics)
    SDK->>API: POST /v1/runs/{id}/results (or background worker trigger)
    API->>DB: Update run results & calculated metric scores
    API-->>SDK: 200 OK
```
