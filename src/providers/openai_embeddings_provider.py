"""
OpenAI Embeddings Provider
Industry-standard embeddings for RAG and semantic search
"""

from typing import List, Optional
from openai import OpenAI
from src.providers.base_embeddings import (
    BaseEmbeddingsProvider,
    EmbeddingsResponse,
    EmbeddingsProviderConfig
)
from src.utils.logger import logger


class OpenAIEmbeddingsProvider(BaseEmbeddingsProvider):
    """OpenAI embeddings provider implementation"""

    @property
    def provider_name(self) -> str:
        return "openai_embeddings"

    def is_available(self) -> bool:
        return bool(self.config.api_key)

    def _get_client(self) -> OpenAI:
        """Lazy client initialization"""
        if not self._client and self.config.api_key:
            self._client = OpenAI(api_key=self.config.api_key)
        return self._client

    async def generate_embeddings(
        self,
        texts: List[str],
        model: Optional[str] = None,
        **kwargs
    ) -> EmbeddingsResponse:
        """Generate embeddings using OpenAI"""
        if not self.is_available():
            raise ValueError("OpenAI API key not configured")

        if not texts:
            raise ValueError("texts cannot be empty")

        client = self._get_client()
        model = model or self.config.default_model or "text-embedding-3-small"

        try:
            # Call OpenAI Embeddings API
            response = client.embeddings.create(
                input=texts,
                model=model,
                encoding_format=kwargs.get('encoding_format', 'float'),  # float or base64
                dimensions=kwargs.get('dimensions')  # Optional: reduce dimensions for smaller vectors
            )

            # Extract embeddings
            embeddings = [item.embedding for item in response.data]
            dimensions = len(embeddings[0]) if embeddings else 0

            # Get token count from response
            total_tokens = response.usage.total_tokens

            # Calculate cost
            cost_usd = self.calculate_cost(model, total_tokens)

            logger.info(
                "openai_embeddings_success",
                model=model,
                texts_count=len(texts),
                dimensions=dimensions,
                total_tokens=total_tokens,
                cost_usd=cost_usd
            )

            return EmbeddingsResponse(
                embeddings=embeddings,
                dimensions=dimensions,
                model=response.model,
                total_tokens=total_tokens,
                cost_usd=cost_usd,
                provider_metadata={
                    "object": response.object
                }
            )

        except Exception as e:
            logger.error(f"OpenAI embeddings error: {str(e)}")
            raise

    def get_models(self) -> List[str]:
        return [
            "text-embedding-3-small",
            "text-embedding-3-large",
            "text-embedding-ada-002"
        ]


# Auto-register this provider
def register():
    # Note: We'll need a separate embeddings registry
    # For now, this creates the class that can be instantiated
    pass
