from abc import ABC, abstractmethod

class BaseEvaluator(ABC):
    """
    Abstract Base Class for Aegis custom metric plugins.
    Implement this class to define custom rule assertion scoring.
    """
    @property
    @abstractmethod
    def metric_name(self) -> str:
        """The user-facing name of the metric."""
        pass

    @property
    @abstractmethod
    def metric_type(self) -> str:
        """The metric type classification, e.g. 'CUSTOM_RULE'."""
        pass

    @abstractmethod
    def score(self, prompt: str, expected: str, actual: str, context_documents: list[str] = None) -> tuple[float, str]:
        """
        Executes evaluation.
        Returns:
            Tuple of (score: float, explanation: str)
        """
        pass
