"""
Embeddings Service - Multi-provider embeddings with cost tracking
Supports OpenAI and Cohere embeddings for RAG and semantic search
"""

from typing import List, Optional, Dict, Any
from pathlib import Path
import yaml

from src.providers.openai_embeddings_provider import OpenAIEmbeddingsProvider
from src.providers.cohere_embeddings_provider import CohereEmbeddingsProvider
from src.providers.base_embeddings import (
    BaseEmbeddingsProvider,
    EmbeddingsProviderConfig,
    EmbeddingsResponse
)
from src.config.settings import settings
from src.utils.logger import logger


class EmbeddingsService:
    """
    Core service for embeddings generation with multi-provider support

    Supports OpenAI and Cohere embeddings for RAG and semantic search use cases
    """

    def __init__(self):
        """Initialize all available embeddings providers"""
        self.providers: Dict[str, BaseEmbeddingsProvider] = {}
        self._initialize_providers()

    def _initialize_providers(self):
        """Load provider configurations and initialize"""
        # Load pricing config
        pricing_config = self._load_pricing_config()

        # Initialize OpenAI Embeddings
        if settings.OPENAI_API_KEY:
            openai_config = EmbeddingsProviderConfig(
                name="openai_embeddings",
                api_key=settings.OPENAI_API_KEY,
                default_model="text-embedding-3-small",
                pricing=pricing_config.get("openai_embeddings", {})
            )
            self.providers["openai"] = OpenAIEmbeddingsProvider(openai_config)
            logger.info("Initialized OpenAI embeddings provider")

        # Initialize Cohere Embeddings
        if settings.COHERE_API_KEY:
            cohere_config = EmbeddingsProviderConfig(
                name="cohere_embeddings",
                api_key=settings.COHERE_API_KEY,
                default_model="embed-english-v3.0",
                pricing=pricing_config.get("cohere_embeddings", {})
            )
            self.providers["cohere"] = CohereEmbeddingsProvider(cohere_config)
            logger.info("Initialized Cohere embeddings provider")

        if not self.providers:
            logger.warning("No embeddings providers configured - set OPENAI_API_KEY or COHERE_API_KEY")
        else:
            logger.info(f"Embeddings service initialized with providers: {', '.join(self.providers.keys())}")

    def _load_pricing_config(self) -> Dict[str, Any]:
        """Load pricing from YAML config file"""
        pricing_file = Path(__file__).parent.parent / "config" / "provider_pricing.yaml"

        if not pricing_file.exists():
            logger.warning("Pricing config not found, using defaults")
            return {}

        try:
            with open(pricing_file) as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load pricing config: {e}")
            return {}

    async def generate_embeddings(
        self,
        texts: List[str],
        provider: Optional[str] = None,
        model: Optional[str] = None,
        **kwargs
    ) -> EmbeddingsResponse:
        """
        Generate embeddings using specified provider

        Args:
            texts: List of text strings to embed
            provider: 'openai' or 'cohere' (defaults to 'cohere' if available)
            model: Model identifier (uses provider default if not specified)
            **kwargs: Provider-specific parameters:
                - input_type (Cohere): 'search_document', 'search_query', 'classification', 'clustering'
                - encoding_format (OpenAI): 'float' or 'base64'
                - dimensions (OpenAI): Optional dimension reduction
                - truncate (Cohere): 'NONE', 'START', 'END'

        Returns:
            EmbeddingsResponse with embeddings, dimensions, tokens, and cost

        Raises:
            ValueError: If provider not available or texts empty
            Exception: On API errors
        """
        if not texts:
            raise ValueError("texts cannot be empty")

        # Select provider
        if provider:
            provider = provider.lower()
            if provider not in self.providers:
                available = list(self.providers.keys())
                raise ValueError(
                    f"Provider '{provider}' not available. "
                    f"Available: {', '.join(available)}"
                )
        else:
            # Default to Cohere if available (better for RAG), else OpenAI
            if "cohere" in self.providers:
                provider = "cohere"
            elif "openai" in self.providers:
                provider = "openai"
            else:
                raise ValueError("No embeddings providers configured")

        # Get provider instance
        provider_instance = self.providers[provider]

        # Generate embeddings
        try:
            response = await provider_instance.generate_embeddings(
                texts=texts,
                model=model,
                **kwargs
            )

            logger.info(
                "embeddings_generation_success",
                provider=provider,
                model=response.model,
                texts_count=len(texts),
                dimensions=response.dimensions,
                total_tokens=response.total_tokens,
                cost_usd=response.cost_usd
            )

            return response

        except Exception as e:
            logger.error(
                "embeddings_generation_failed",
                provider=provider,
                model=model,
                texts_count=len(texts),
                error=str(e)
            )
            raise

    def get_available_providers(self) -> List[str]:
        """Get list of available embeddings providers"""
        return list(self.providers.keys())

    def get_provider_models(self, provider: str) -> List[str]:
        """Get supported models for a provider"""
        provider = provider.lower()
        if provider not in self.providers:
            return []
        return self.providers[provider].get_models()


# Create global instance
embeddings_service = EmbeddingsService()
