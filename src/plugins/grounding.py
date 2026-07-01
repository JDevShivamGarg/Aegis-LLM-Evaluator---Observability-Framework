import re
import numpy as np
from sentence_transformers import SentenceTransformer
from src.core.config import settings
from src.services.base_evaluator import BaseEvaluator

_similarity_model = None

class GroundingEvaluator(BaseEvaluator):
    """
    Evaluates the grounding (faithfulness) of actual outputs relative to
    the retrieved 'context_documents' list, detecting hallucinations.
    """
    @property
    def metric_name(self) -> str:
        return "RAG Grounding Score"

    @property
    def metric_type(self) -> str:
        return "GROUNDING_EVALUATOR"

    def score(self, prompt: str, expected: str, actual: str, context_documents: list[str] = None) -> tuple[float, str]:
        global _similarity_model
        
        # Guard clause: if context_documents is empty or None
        if not context_documents:
            return 1.0, "No context documents provided. Grounding assumed."

        if not actual:
            return 1.0, "Empty output, grounding check skipped."

        if _similarity_model is None:
            try:
                # Load similarity model, cached locally
                _similarity_model = SentenceTransformer(settings.EMBEDDING_MODEL_PATH)
            except Exception as e:
                print(f"Error loading grounding SentenceTransformer: {e}")
                return 0.0, f"Embedding model loading failed: {e}"

        try:
            # 1. Segment actual output into sentences
            sentences = [s.strip() for s in re.split(r'(?<=[.!?]) +', actual) if s.strip()]
            if not sentences:
                return 1.0, "No valid sentences to evaluate grounding."

            # 2. Get embeddings for context documents and output sentences
            doc_embeddings = _similarity_model.encode(context_documents)
            sentence_embeddings = _similarity_model.encode(sentences)

            # 3. Calculate cosine similarities
            ungrounded_sentences = []
            similarities = []

            for idx, sent_emb in enumerate(sentence_embeddings):
                # Calculate cosine similarity with all doc chunks
                norms_docs = np.linalg.norm(doc_embeddings, axis=1)
                norm_sent = np.linalg.norm(sent_emb)
                
                if norm_sent == 0 or np.any(norms_docs == 0):
                    max_sim = 0.0
                else:
                    dot_products = np.dot(doc_embeddings, sent_emb)
                    sim_scores = dot_products / (norms_docs * norm_sent)
                    max_sim = float(np.max(sim_scores))
                
                similarities.append(max_sim)
                
                # Flag sentence as ungrounded if max similarity is low
                if max_sim < 0.60:
                    ungrounded_sentences.append(f"'{sentences[idx]}' (Score: {max_sim:.3f})")

            # Final score is the mean of maximum sentence similarity scores
            mean_grounding_score = float(np.mean(similarities))
            
            # Format explanation
            if ungrounded_sentences:
                explanation = f"Potential hallucinations found. Ungrounded sentences: {'; '.join(ungrounded_sentences[:3])}"
                if len(ungrounded_sentences) > 3:
                    explanation += f" (+{len(ungrounded_sentences) - 3} more)"
            else:
                explanation = "All sentences are semantically grounded in the context documents."

            return round(mean_grounding_score, 4), explanation

        except Exception as err:
            return 0.0, f"Grounding evaluation failed: {err}"
