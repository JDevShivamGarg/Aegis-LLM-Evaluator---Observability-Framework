import re
from openai import OpenAI
from src.core.config import settings

class LLMJudgeEvaluator:
    """Invokes an LLM to judge the quality of actual output against expectations and prompts."""
    def __init__(self, provider: str = "groq", model: str = None, api_key: str = None, base_url: str = None):
        self.provider = provider.lower()
        if self.provider == "groq":
            self.client = OpenAI(
                api_key=api_key or settings.GROQ_API_KEY,
                base_url=base_url or "https://api.groq.com/openai/v1"
            )
            self.model = model or "llama-3.1-8b-instant"
        else:
            self.client = OpenAI(
                api_key=api_key or settings.OPENAI_API_KEY,
                base_url=base_url or "https://api.openai.com/v1"
            )
            self.model = model or "gpt-4o-mini"

    def judge(self, prompt: str, expected: str | None, actual: str) -> tuple[float, str]:
        """
        Calls the LLM Judge.
        Returns:
            (score, explanation)
        """
        system_instructions = (
            "You are a strict, objective, and expert quality assurance judge.\n"
            "Analyze the actual output of an AI agent based on the user prompt and the gold expected output (if provided).\n"
            "Rate the actual output quality on a scale of 0.0 (totally incorrect or harmful) to 1.0 (perfectly correct and helpful).\n"
            "Format your response EXACTLY as follows with XML tags:\n"
            "<explanation>Detail your reasoning here</explanation>\n"
            "<score>0.85</score>"
        )

        user_content = (
            f"User Prompt: {prompt}\n"
            f"Expected Gold Output: {expected if expected else 'Not specified'}\n"
            f"Actual Output: {actual}\n"
        )

        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_instructions},
                    {"role": "user", "content": user_content}
                ],
                temperature=0.0,
                max_tokens=500
            )
            response_text = response.choices[0].message.content
            return self.parse_judge_response(response_text)
        except Exception as e:
            return 0.0, f"Error calling judge LLM API: {str(e)}"

    @staticmethod
    def parse_judge_response(response_text: str) -> tuple[float, str]:
        """Extracts a numeric score and explanation from the XML structured response."""
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
            # Fallback: grab anything outside tags
            explanation = re.sub(r"<score>.*?</score>", "", response_text, flags=re.IGNORECASE | re.DOTALL).strip()
            
        return score, explanation
