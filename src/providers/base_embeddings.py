"""
Base Embeddings Provider Interface
All embeddings providers must implement this protocol
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field


@dataclass
class EmbeddingsResponse:
    """Standardized response from any embeddings provider"""
    embeddings: List[List[float]]
    dimensions: int
    model: str
    total_tokens: int
    cost_usd: float
    provider_metadata: Optional[Dict[str, Any]] = field(default_factory=dict)


@dataclass
class EmbeddingsProviderConfig:
    """Embeddings provider configuration"""
    name: str
    api_key: Optional[str]
    base_url: Optional[str] = None
    default_model: Optional[str] = None
    timeout: int = 60
    pricing: Optional[Dict[str, float]] = field(default_factory=dict)


class BaseEmbeddingsProvider(ABC):
    """
    Abstract base class for embeddings providers

    All providers must implement:
    - is_available(): Check if provider is configured
    - generate_embeddings(): Generate vector embeddings
    - get_models(): Return supported embedding models
    """

    def __init__(self, config: EmbeddingsProviderConfig):
        self.config = config
        self._client = None

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Unique provider identifier (e.g., 'openai_embeddings', 'cohere_embeddings')"""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider is properly configured"""
        pass

    @abstractmethod
    async def generate_embeddings(
        self,
        texts: List[str],
        model: Optional[str] = None,
        **kwargs
    ) -> EmbeddingsResponse:
        """
        Generate vector embeddings for text inputs

        Args:
            texts: List of text strings to embed
            model: Optional model override
            **kwargs: Provider-specific parameters

        Returns:
            EmbeddingsResponse with standardized fields

        Raises:
            ValueError: If provider not configured or invalid params
            Exception: On API errors
        """
        pass

    @abstractmethod
    def get_models(self) -> List[str]:
        """Return list of supported embedding model identifiers"""
        pass

    def calculate_cost(
        self,
        model: str,
        total_tokens: int
    ) -> float:
        """
        Calculate cost based on token usage

        Embeddings pricing is typically per 1K tokens (single rate, not input/output)
        """
        if not self.config.pricing or model not in self.config.pricing:
            # Fallback: find closest match by model name substring
            for model_pattern, cost_per_1k in (self.config.pricing or {}).items():
                if model_pattern.lower() in model.lower():
                    return round((total_tokens / 1000) * cost_per_1k, 6)

            # Final fallback
            return round((total_tokens / 1000) * 0.0001, 6)

        cost_per_1k = self.config.pricing[model]
        return round((total_tokens / 1000) * cost_per_1k, 6)
