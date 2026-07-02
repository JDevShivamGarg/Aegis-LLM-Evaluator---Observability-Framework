# Aegis SDK Integration Guide

The Aegis Python SDK provides two classes to integrate LLM evaluation and observability into your single-agent or multi-agent loops and tool pipelines.

---

## 1. Local In-Memory Evaluation (`AegisLocalEvaluator`)

Use `AegisLocalEvaluator` inside your active agent loops to check model outputs synchronously before responding to client requests. This runs locally on the host machine, requiring no database connections or external networking dependencies.

### Usage Example: Validating JSON tool output before parsing

```python
import json
from src.sdk.client import AegisLocalEvaluator

agent_output = '{"route": "Support", "reason": "My shipping query"}'

# 1. Assert valid JSON syntax
is_json, reason = AegisLocalEvaluator.check_rule("is_json", True, agent_output)
if is_json == 0.0:
    print(f"JSON validation failed: {reason}")
    # Trigger retry or fallback formatting

# 2. Enforce strict schema constraints
schema = {
    "type": "object",
    "properties": {
        "route": {"type": "string", "enum": ["Billing", "Support", "Returns"]},
        "reason": {"type": "string"}
    },
    "required": ["route", "reason"]
}
schema_valid, reason = AegisLocalEvaluator.check_rule("json_schema", schema, agent_output)
if schema_valid == 0.0:
    print(f"Schema validation failed: {reason}")

# 3. Check local semantic cosine similarity
expected = '{"route": "Support", "reason": "shipping delay query"}'
similarity = AegisLocalEvaluator.check_semantic_similarity(expected, agent_output)
print(f"Semantic similarity: {similarity:.4f}")
```

---

## 2. Remote API Telemetry Logging (`AegisAPIClient`)

Use `AegisAPIClient` to register test runs and capture evaluation results in the central PostgreSQL database. This is ideal for logging session traces, latency metrics, and prompt performance across model versions.

### Usage Example: Logging agent runs

```python
from src.sdk.client import AegisAPIClient

# Initialize client
client = AegisAPIClient(base_url="http://127.0.0.1:8000")

# 1. Setup metadata
project = client.create_project(name="CS Agent", description="Customer Support")
suite = client.create_suite(project_id=project["id"], name="General Audit")

# 2. Upload test cases
client.upload_cases(
    suite_id=suite["id"],
    cases=[
        {
            "input_prompt": "My credit card was charged twice.",
            "expected_output": "I will check the double charge...",
            "assertion_rules": [{"type": "contains", "value": "charge"}]
        }
    ]
)

# 3. Trigger evaluation run
run = client.trigger_run(
    suite_id=suite["id"],
    model_name="llama-3.1-8b-instant",
    prompt_version="v1.0-prod"
)
print(f"Triggered Run ID: {run['run_id']}")
```

---

## 3. Framework Telemetry Callbacks

Aegis includes pre-built callback integrations to automatically record prompts, completions, and token usages from popular Python agentic frameworks.

### A. LangChain Integration (`AegisLangChainCallback`)

Pass the Aegis callback handler to your chain execution blocks:

```python
from langchain_openai import ChatOpenAI
from src.services.callbacks import AegisLangChainCallback

# Initialize the callback handler
aegis_callback = AegisLangChainCallback(
    base_url="http://127.0.0.1:8000",
    suite_id="<TEST_SUITE_UUID>",
    prompt_version="v1.4-rag-eval",
    auth_token="<JWT_BEARER_TOKEN>"
)

# Pass the handler to the LLM or Chain call
llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.0,
    callbacks=[aegis_callback]
)

response = llm.invoke("What is the refund policy for active subscriptions?")
print(response.content)
```

### B. CrewAI Integration (`AegisCrewAICallback`)

Hook task completions to log agent telemetry:

```python
from crewai import Agent, Task, Crew
from src.services.callbacks import AegisCrewAICallback

aegis_crew_callback = AegisCrewAICallback(
    base_url="http://127.0.0.1:8000",
    suite_id="<TEST_SUITE_UUID>",
    prompt_version="v1.1-crew",
    auth_token="<JWT_BEARER_TOKEN>"
)

# Capture task outcomes asynchronously
task_output = "The customer's transaction logs indicate..."
aegis_crew_callback.after_agent_execution(
    agent_name="Triage Specialist",
    task_description="Verify double charge",
    result_output=task_output,
    model_name="llama-3.1-8b-instant"
)
```

---

## 4. Batch Test Case Uploading via API

To upload large evaluation datasets containing edge cases, you can POST a `.csv` or `.jsonl` file directly to the Central API Server.

### A. Uploading CSV Files
Ensure your CSV file contains columns for `input_prompt`, `expected_output`, and `assertion_rules` (formatted as a JSON string):
```bash
curl -X POST "http://localhost:8000/v1/suites/<TEST_SUITE_UUID>/upload" \
     -H "Authorization: Bearer <JWT_ACCESS_TOKEN>" \
     -F "file=@/path/to/test_cases.csv"
```

### B. Uploading JSONL Files
Each line of the JSONL file must be a standalone JSON object:
```bash
curl -X POST "http://localhost:8000/v1/suites/<TEST_SUITE_UUID>/upload" \
     -H "Authorization: Bearer <JWT_ACCESS_TOKEN>" \
     -F "file=@/path/to/test_cases.jsonl"
```


