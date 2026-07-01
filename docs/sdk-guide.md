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
