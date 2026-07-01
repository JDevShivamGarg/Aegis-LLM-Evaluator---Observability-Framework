from sqlalchemy.orm import Session
from src.core.models import ProviderPricing

# Default fallback pricing (USD per 1,000 tokens)
DEFAULT_PRICING = {
    # Groq models
    "llama-3.1-8b-instant": {"input": 0.00005, "output": 0.00008},
    "llama-3.3-70b-versatile": {"input": 0.00059, "output": 0.00079},
    "llama3-70b-8192": {"input": 0.00059, "output": 0.00079},
    # OpenAI models
    "gpt-4o-mini": {"input": 0.00015, "output": 0.00060},
    "gpt-4o": {"input": 0.00500, "output": 0.01500},
}

def calculate_token_cost(db: Session, model_name: str, prompt_tokens: int, completion_tokens: int) -> float:
    """
    Computes estimated token costs in USD for a given model.
    Checks the database provider_pricing configuration first, falling back to defaults.
    """
    if not model_name:
        return 0.0

    # Search in database first
    pricing = db.query(ProviderPricing).filter(ProviderPricing.model_name == model_name).first()
    
    if pricing:
        input_rate = pricing.input_cost_per_1k
        output_rate = pricing.output_cost_per_1k
    else:
        # Fallback to hardcoded defaults
        model_key = model_name.lower().strip()
        rates = DEFAULT_PRICING.get(model_key, {"input": 0.00015, "output": 0.00060})  # default to gpt-4o-mini rate
        input_rate = rates["input"]
        output_rate = rates["output"]

    # Compute total cost (rate is per 1000 tokens)
    input_cost = (prompt_tokens / 1000.0) * input_rate
    output_cost = (completion_tokens / 1000.0) * output_rate
    
    return round(input_cost + output_cost, 6)
