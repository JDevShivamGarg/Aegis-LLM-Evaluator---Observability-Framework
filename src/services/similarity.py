import numpy as np

class EmbeddingSimilarityEvaluator:
    """Calculates cosine similarity between expected and actual outputs using a local model."""
    def __init__(self, model):
        # model is a SentenceTransformer instance loaded locally
        self.model = model

    def score(self, expected: str, actual: str) -> float:
        if not expected or not actual:
            return 0.0
        
        try:
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
        except Exception:
            return 0.0
