import requests
from typing import List, Dict, Any, Optional
from sentence_transformers import SentenceTransformer
from src.core.config import settings
from src.services.rules import evaluate_rule
from src.services.similarity import EmbeddingSimilarityEvaluator
from src.services.judge import LLMJudgeEvaluator

# Global cache for local sentence-transformers model to avoid reload penalty
_local_similarity_evaluator = None

class AegisLocalEvaluator:
    """
    Runs evaluations synchronously in-memory.
    Ideal for agents to inspect and check their own outputs inline
    without database dependencies.
    """
    @staticmethod
    def check_rule(rule_type: str, rule_value: Any, actual_output: str) -> tuple[float, str]:
        """Runs a single regex, contains, JSON, or schema assertion check."""
        return evaluate_rule(rule_type, rule_value, actual_output)

    @staticmethod
    def check_semantic_similarity(expected_output: str, actual_output: str) -> float:
        """Calculates cosine similarity locally using Sentence-Transformers."""
        global _local_similarity_evaluator
        if _local_similarity_evaluator is None:
            try:
                model = SentenceTransformer(settings.EMBEDDING_MODEL_PATH)
                _local_similarity_evaluator = EmbeddingSimilarityEvaluator(model)
            except Exception as e:
                print(f"Error loading local SentenceTransformer: {e}")
                return 0.0
        return _local_similarity_evaluator.score(expected_output, actual_output)

    @staticmethod
    def check_llm_judge(prompt: str, expected_output: Optional[str], actual_output: str, provider: str = "groq") -> tuple[float, str]:
        """Invokes LLM-as-judge scoring and explanation."""
        evaluator = LLMJudgeEvaluator(provider=provider)
        return evaluator.judge(prompt, expected_output, actual_output)


class AegisAPIClient:
    """
    HTTP client wrapper for the Aegis REST API.
    Use this to log runs and register evaluations from agent sessions.
    """
    def __init__(self, base_url: str = "http://127.0.0.1:8000"):
        self.base_url = base_url.rstrip("/")

    def create_project(self, name: str, description: Optional[str] = None) -> Dict[str, Any]:
        response = requests.post(
            f"{self.base_url}/v1/projects",
            json={"name": name, "description": description}
        )
        response.raise_for_status()
        return response.json()

    def create_suite(self, project_id: str, name: str, description: Optional[str] = None) -> Dict[str, Any]:
        response = requests.post(
            f"{self.base_url}/v1/projects/{project_id}/suites",
            json={"name": name, "description": description}
        )
        response.raise_for_status()
        return response.json()

    def upload_cases(self, suite_id: str, cases: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Uploads cases payload format:
        cases = [
            {
                "input_prompt": "prompt text",
                "expected_output": "expected text",
                "assertion_rules": [{"type": "contains", "value": "x"}]
            }
        ]
        """
        response = requests.post(
            f"{self.base_url}/v1/suites/{suite_id}/cases",
            json={"cases": cases}
        )
        response.raise_for_status()
        return response.json()

    def trigger_run(self, suite_id: str, model_name: str, prompt_version: str) -> Dict[str, Any]:
        response = requests.post(
            f"{self.base_url}/v1/runs",
            json={
                "suite_id": suite_id,
                "model_name": model_name,
                "prompt_version": prompt_version
            }
        )
        response.raise_for_status()
        return response.json()

    def get_run_status(self, run_id: str) -> Dict[str, Any]:
        response = requests.get(f"{self.base_url}/v1/runs/{run_id}")
        response.raise_for_status()
        return response.json()

    def get_run_results(self, run_id: str) -> Dict[str, Any]:
        response = requests.get(f"{self.base_url}/v1/runs/{run_id}/results")
        response.raise_for_status()
        return response.json()
