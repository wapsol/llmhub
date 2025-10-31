"""
Cohere Embeddings Provider
High-quality embeddings for RAG and semantic search
"""

from typing import List, Optional
import cohere
from src.providers.base_embeddings import (
    BaseEmbeddingsProvider,
    EmbeddingsResponse,
    EmbeddingsProviderConfig
)
from src.utils.logger import logger


class CohereEmbeddingsProvider(BaseEmbeddingsProvider):
    """Cohere embeddings provider implementation"""

    @property
    def provider_name(self) -> str:
        return "cohere_embeddings"

    def is_available(self) -> bool:
        return bool(self.config.api_key)

    def _get_client(self) -> cohere.Client:
        """Lazy client initialization"""
        if not self._client and self.config.api_key:
            self._client = cohere.Client(api_key=self.config.api_key)
        return self._client

    async def generate_embeddings(
        self,
        texts: List[str],
        model: Optional[str] = None,
        **kwargs
    ) -> EmbeddingsResponse:
        """Generate embeddings using Cohere"""
        if not self.is_available():
            raise ValueError("Cohere API key not configured")

        if not texts:
            raise ValueError("texts cannot be empty")

        client = self._get_client()
        model = model or self.config.default_model or "embed-english-v3.0"

        try:
            # Call Cohere Embed API
            response = client.embed(
                texts=texts,
                model=model,
                input_type=kwargs.get('input_type', 'search_document'),  # search_document, search_query, classification, clustering
                truncate=kwargs.get('truncate', 'END')  # NONE, START, END
            )

            # Extract embeddings
            embeddings = response.embeddings
            dimensions = len(embeddings[0]) if embeddings else 0

            # Cohere returns meta with billed units
            total_tokens = 0
            if hasattr(response, 'meta') and response.meta:
                if hasattr(response.meta, 'billed_units'):
                    total_tokens = getattr(response.meta.billed_units, 'input_tokens', len(texts) * 100)  # Fallback estimate

            # If no token count, estimate based on text length
            if total_tokens == 0:
                # Rough estimate: ~1 token per 4 characters
                total_tokens = sum(len(text) // 4 for text in texts)

            # Calculate cost
            cost_usd = self.calculate_cost(model, total_tokens)

            logger.info(
                "cohere_embeddings_success",
                model=model,
                texts_count=len(texts),
                dimensions=dimensions,
                total_tokens=total_tokens,
                cost_usd=cost_usd
            )

            return EmbeddingsResponse(
                embeddings=embeddings,
                dimensions=dimensions,
                model=model,
                total_tokens=total_tokens,
                cost_usd=cost_usd,
                provider_metadata={
                    "response_id": getattr(response, 'id', None)
                }
            )

        except Exception as e:
            logger.error(f"Cohere embeddings error: {str(e)}")
            raise

    def get_models(self) -> List[str]:
        return [
            "embed-english-v3.0",
            "embed-multilingual-v3.0",
            "embed-english-light-v3.0",
            "embed-multilingual-light-v3.0"
        ]


# Auto-register this provider
def register():
    from src.providers import ProviderRegistry
    # Note: We'll need a separate embeddings registry
    # For now, this creates the class that can be instantiated
    pass
