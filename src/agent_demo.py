import json
import time
from openai import OpenAI
from src.core.config import settings
from src.sdk.client import AegisLocalEvaluator, AegisAPIClient

def run_agentic_workflow_demo():
    print("=== Starting Agentic Workflow Demo ===")
    
    # 1. Initialize API Client
    api_client = AegisAPIClient(base_url="http://127.0.0.1:8000")
    
    # Check server health
    try:
        health = api_client.get_run_status("00000000-0000-0000-0000-000000000000")
    except Exception:
        # Server is active but status is 404 for invalid UUID, which is fine
        print("Aegis API Server is responsive.")

    # 2. Setup Project and Suite for the Agent
    print("Setting up Agent Evaluation Suite on Aegis Server...")
    project = api_client.create_project(
        name="Support Router Agent Project",
        description="Logs verification runs for the routing agentic workflows."
    )
    proj_id = project["id"]
    
    suite = api_client.create_suite(
        project_id=proj_id,
        name="Routing Quality Suite",
        description="Ensures agent correctly routes query to Billing, Support, or Returns."
    )
    suite_id = suite["id"]

    # Upload the golden evaluation test case
    test_cases = [
        {
            "input_prompt": "My package hasn't arrived yet. Where is it?",
            "expected_output": '{"route": "Support", "reason": "shipping delay query"}',
            "assertion_rules": [
                {"type": "is_json", "value": True},
                {
                    "type": "json_schema",
                    "value": {
                        "type": "object",
                        "properties": {
                            "route": {"type": "string", "enum": ["Billing", "Support", "Returns"]},
                            "reason": {"type": "string"}
                        },
                        "required": ["route", "reason"]
                    }
                }
            ]
        }
    ]
    api_client.upload_cases(suite_id, test_cases)
    print("Agent Evaluation Suite setup complete.")

    # 3. Simulate Agent Execution Loop
    print("\nSimulating Agent Execution...")
    user_query = "My package hasn't arrived yet. Where is it?"
    
    # Call Groq to route the query
    client = OpenAI(
        api_key=settings.GROQ_API_KEY,
        base_url="https://api.groq.com/openai/v1"
    )
    
    prompt = (
        f"You are a routing agent. Route this customer query: '{user_query}'\n"
        "Output ONLY a raw JSON object matching this schema:\n"
        "{\n"
        '  "route": "Billing" | "Support" | "Returns",\n'
        '  "reason": "short explanation"\n'
        "}"
    )

    try:
        response = client.chat.completions.create(
            model="llama-3.1-8b-instant",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.0,
            max_tokens=200
        )
        agent_output = response.choices[0].message.content.strip()
    except Exception as e:
        agent_output = f"Error calling agent: {e}"

    print(f"Agent Raw Output: {agent_output}")

    # 4. Inline/In-Memory Guardrail Check using AegisLocalEvaluator
    print("\nRunning AegisLocalEvaluator guardrails inline...")
    
    # Rule 1: Check JSON structure
    is_json, json_reason = AegisLocalEvaluator.check_rule("is_json", True, agent_output)
    print(f"  JSON structure check: Score={is_json} ({json_reason})")
    
    # Rule 2: Check schema format
    schema = {
        "type": "object",
        "properties": {
            "route": {"type": "string", "enum": ["Billing", "Support", "Returns"]},
            "reason": {"type": "string"}
        },
        "required": ["route", "reason"]
    }
    schema_ok, schema_reason = AegisLocalEvaluator.check_rule("json_schema", schema, agent_output)
    print(f"  JSON schema check: Score={schema_ok} ({schema_reason})")

    # Rule 3: Check Semantic Similarity to Expected
    similarity_score = AegisLocalEvaluator.check_semantic_similarity(
        expected_output='{"route": "Support", "reason": "shipping delay query"}',
        actual_output=agent_output
    )
    print(f"  Semantic Similarity score: {similarity_score:.4f}")

    # 5. Remote Telemetry Registration using AegisAPIClient
    print("\nRegistering Run & Telemetry to Aegis Server...")
    run = api_client.trigger_run(
        suite_id=suite_id,
        model_name="llama-3.1-8b-instant",
        prompt_version="v1.0-prod"
    )
    run_id = run["run_id"]
    print(f"Triggered Run ID: {run_id}")

    # Wait for Celery worker to complete background evaluation run
    print("Waiting for background evaluations to process...")
    time.sleep(12)

    # Get final scores from API
    run_status = api_client.get_run_status(run_id)
    print(f"Run Evaluation status: {run_status['status']}")
    print(f"Run Average Quality score: {run_status['average_score']}")

    results = api_client.get_run_results(run_id)
    print("\nDetailed Metric Scores Saved in Database:")
    for res in results["results"]:
        for score in res["scores"]:
            print(f"  - {score['metric_name']}: Score={score['score']}")

    print("\n=== Agentic SDK Workflow Demo Complete ===")

if __name__ == "__main__":
    run_agentic_workflow_demo()
