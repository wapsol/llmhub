"""
Base Provider Interface
All LLM providers must implement this protocol
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field


@dataclass
class LLMResponse:
    """Standardized response from any provider"""
    content: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    provider_metadata: Optional[Dict[str, Any]] = field(default_factory=dict)


@dataclass
class ProviderMetadata:
    """Provider display metadata for UI"""
    display_name: str
    description: str
    logo_url: Optional[str] = None
    website_url: Optional[str] = None
    requires_api_key: bool = True
    requires_base_url: bool = False


@dataclass
class ProviderConfig:
    """Provider configuration and pricing"""
    name: str
    api_key: Optional[str]
    base_url: Optional[str] = None
    default_model: Optional[str] = None
    timeout: int = 60
    pricing: Optional[Dict[str, Dict[str, float]]] = field(default_factory=dict)


class BaseProvider(ABC):
    """
    Abstract base class for LLM providers

    All providers must implement:
    - is_available(): Check if provider is configured
    - call(): Make API call with standardized interface
    - get_models(): Return supported models
    """

    def __init__(self, config: ProviderConfig):
        self.config = config
        self._client = None

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Unique provider identifier (e.g., 'claude', 'openai')"""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Check if provider is properly configured"""
        pass

    @abstractmethod
    async def call(
        self,
        model: str,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Make LLM API call

        Returns:
            LLMResponse with standardized fields

        Raises:
            ValueError: If provider not configured or invalid params
            Exception: On API errors
        """
        pass

    @abstractmethod
    def get_models(self) -> List[str]:
        """Return list of supported model identifiers"""
        pass

    @abstractmethod
    def get_metadata(self) -> "ProviderMetadata":
        """Return provider metadata for UI display"""
        pass

    def calculate_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int
    ) -> float:
        """
        Calculate cost based on token usage

        Pricing loaded from config, so adding new models doesn't require code changes
        """
        if not self.config.pricing or model not in self.config.pricing:
            # Fallback: find closest match by model name substring
            for model_pattern, costs in (self.config.pricing or {}).items():
                if model_pattern.lower() in model.lower():
                    input_cost = (input_tokens / 1000) * costs.get("input", 0.01)
                    output_cost = (output_tokens / 1000) * costs.get("output", 0.03)
                    return round(input_cost + output_cost, 6)

            # Final fallback
            return round((input_tokens / 1000) * 0.01 + (output_tokens / 1000) * 0.03, 6)

        costs = self.config.pricing[model]
        input_cost = (input_tokens / 1000) * costs["input"]
        output_cost = (output_tokens / 1000) * costs["output"]
        return round(input_cost + output_cost, 6)
