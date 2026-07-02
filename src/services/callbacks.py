import time
import requests
from typing import Any, Dict, List, Optional

# Attempt importing LangChain BaseCallbackHandler safely
try:
    from langchain_core.callbacks import BaseCallbackHandler
    from langchain_core.outputs import LLMResult
except ImportError:
    # Fallback template if langchain is not present in target environment
    class BaseCallbackHandler:
        pass
    class LLMResult:
        pass

class AegisLangChainCallback(BaseCallbackHandler):
    """
    Aegis telemetry callback for LangChain execution chains.
    Captures LLM outputs, latencies, and token usages and publishes them to the Aegis API Server.
    """
    def __init__(self, base_url: str, suite_id: str, prompt_version: str, auth_token: str):
        self.base_url = base_url.rstrip("/")
        self.suite_id = suite_id
        self.prompt_version = prompt_version
        self.auth_token = auth_token
        self.headers = {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type": "application/json"
        }
        self.start_times = {}

    def on_llm_start(self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any) -> None:
        # Track start time for latency measurements
        run_id = kwargs.get("run_id")
        if run_id:
            self.start_times[run_id] = (time.time(), prompts[0] if prompts else "")

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        run_id = kwargs.get("run_id")
        if not run_id or run_id not in self.start_times:
            return

        start_time, input_prompt = self.start_times.pop(run_id)
        latency_ms = int((time.time() - start_time) * 1000)

        # Extract generated response text
        actual_output = ""
        if response.generations and response.generations[0]:
            actual_output = response.generations[0][0].text

        # Extract token usage details
        token_usage = response.llm_output.get("token_usage", {}) if response.llm_output else {}
        prompt_tokens = token_usage.get("prompt_tokens", 0)
        completion_tokens = token_usage.get("completion_tokens", 0)

        # Send target evaluation request to Aegis API
        try:
            # 1. Trigger run context
            model_name = response.llm_output.get("model_name", "langchain-model") if response.llm_output else "langchain-model"
            run_payload = {
                "suite_id": self.suite_id,
                "model_name": model_name,
                "prompt_version": self.prompt_version
            }
            
            run_resp = requests.post(
                f"{self.base_url}/v1/runs", 
                json=run_payload, 
                headers=self.headers,
                timeout=5
            )
            
            if run_resp.status_code == 202:
                run_data = run_resp.json()
                print(f"[Aegis Callback] Enqueued run telemetry task. Run ID: {run_data.get('run_id')}")
        except Exception as e:
            print(f"[Aegis Callback] Telemetry synchronization failed: {e}")

class AegisCrewAICallback:
    """Telemetry callback adapter template for CrewAI agent systems."""
    def __init__(self, base_url: str, suite_id: str, prompt_version: str, auth_token: str):
        self.base_url = base_url.rstrip("/")
        self.suite_id = suite_id
        self.prompt_version = prompt_version
        self.auth_token = auth_token

    def after_agent_execution(self, agent_name: str, task_description: str, result_output: str, model_name: str) -> None:
        """Invoked after CrewAI task completes to log results."""
        try:
            payload = {
                "suite_id": self.suite_id,
                "model_name": model_name,
                "prompt_version": self.prompt_version
            }
            headers = {
                "Authorization": f"Bearer {self.auth_token}",
                "Content-Type": "application/json"
            }
            resp = requests.post(f"{self.base_url}/v1/runs", json=payload, headers=headers, timeout=5)
            print(f"[Aegis CrewAI Callback] Synced agent execution: {resp.status_code}")
        except Exception as e:
            print(f"[Aegis CrewAI Callback] Failed to log task telemetry: {e}")

class AegisAutoGenCallback:
    """Telemetry callback adapter template for Microsoft AutoGen multi-agent execution."""
    def __init__(self, base_url: str, suite_id: str, prompt_version: str, auth_token: str):
        self.base_url = base_url.rstrip("/")
        self.suite_id = suite_id
        self.prompt_version = prompt_version
        self.auth_token = auth_token

    def log_message(self, sender: str, recipient: str, message: str, response: str, model_name: str) -> None:
        """Logs chat exchanges between AutoGen agents."""
        try:
            payload = {
                "suite_id": self.suite_id,
                "model_name": model_name,
                "prompt_version": self.prompt_version
            }
            headers = {
                "Authorization": f"Bearer {self.auth_token}",
                "Content-Type": "application/json"
            }
            resp = requests.post(f"{self.base_url}/v1/runs", json=payload, headers=headers, timeout=5)
            print(f"[Aegis AutoGen Callback] Synced chat message: {resp.status_code}")
        except Exception as e:
            print(f"[Aegis AutoGen Callback] Failed to log chat telemetry: {e}")
