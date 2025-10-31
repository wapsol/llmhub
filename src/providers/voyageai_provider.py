"""
VoyageAI Provider - Embeddings and Reranking
Premium semantic search and retrieval provider
"""

from typing import Dict, Any, List, Optional, Union
import os

from src.providers.base import BaseProvider, LLMResponse, ProviderConfig, ProviderMetadata
from src.utils.logger import logger


class VoyageAIProvider(BaseProvider):
    """
    VoyageAI embeddings and reranking provider

    Supports:
    - Text embeddings (6 models): General-purpose and domain-specific
    - Document reranking (2 models): Refine search results
    - Matryoshka embeddings: Flexible output dimensions
    - Asymmetric embeddings: Optimized for queries vs documents

    Operations:
    - embed: Generate semantic vectors from text(s)
    - rerank: Score documents by relevance to query
    """

    # Embedding models
    EMBEDDING_MODELS = [
        "voyage-3.5",           # Best cost/performance ($0.06/1M tokens)
        "voyage-3.5-lite",      # Ultra-cheap ($0.02/1M tokens)
        "voyage-3-large",       # Highest quality ($0.18/1M tokens)
        "voyage-code-3",        # Code search ($0.18/1M tokens)
        "voyage-finance-2",     # Financial documents ($0.12/1M tokens)
        "voyage-law-2",         # Legal documents ($0.12/1M tokens)
    ]

    # Reranking models
    RERANK_MODELS = [
        "rerank-2.5",           # Best quality ($0.05/1M tokens)
        "rerank-2.5-lite",      # Faster/cheaper ($0.02/1M tokens)
    ]

    @property
    def provider_name(self) -> str:
        return "voyageai"

    def is_available(self) -> bool:
        """Check if VoyageAI API key is configured"""
        return self.config.api_key is not None and len(self.config.api_key) > 0

    def get_models(self) -> List[str]:
        """Return all supported models (embeddings + reranking)"""
        return self.EMBEDDING_MODELS + self.RERANK_MODELS

    def get_metadata(self) -> ProviderMetadata:
        """Provider information for UI display"""
        return ProviderMetadata(
            display_name="Voyage AI",
            description="Premium embeddings and reranking for semantic search and RAG",
            logo_url="https://www.voyageai.com/logo.png",
            website_url="https://www.voyageai.com",
            requires_api_key=True,
            requires_base_url=False
        )

    def _get_client(self):
        """Lazy-load VoyageAI client"""
        if self._client is None:
            try:
                import voyageai

                # Set API key in environment (required by voyageai SDK)
                if self.config.api_key:
                    os.environ['VOYAGE_API_KEY'] = self.config.api_key

                self._client = voyageai.Client(api_key=self.config.api_key)
                logger.info(f"Initialized VoyageAI client")
            except ImportError:
                raise ImportError(
                    "voyageai package not installed. "
                    "Install with: pip install voyageai"
                )
            except Exception as e:
                logger.error(f"Failed to initialize VoyageAI client: {str(e)}")
                raise

        return self._client

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
        Route to embedding or reranking based on operation kwarg

        Operations:
        - embed: Generate embeddings (texts kwarg required)
        - rerank: Rerank documents (query and documents kwargs required)
        """
        if not self.is_available():
            raise ValueError(
                "VoyageAI provider not configured. "
                "Set VOYAGE_API_KEY in .env"
            )

        operation = kwargs.get("operation", "embed")

        if operation == "embed":
            return await self._embed(model, **kwargs)
        elif operation == "rerank":
            return await self._rerank(model, **kwargs)
        else:
            raise ValueError(
                f"Unknown operation '{operation}'. "
                f"Supported: embed, rerank"
            )

    async def _embed(
        self,
        model: str,
        texts: Union[str, List[str]] = None,
        input_type: Optional[str] = None,
        output_dimension: Optional[int] = None,
        truncation: Optional[bool] = True,
        **kwargs
    ) -> LLMResponse:
        """
        Generate embeddings for text(s)

        Args:
            model: Embedding model name
            texts: Single text or list of texts to embed
            input_type: "document", "query", or None (optimizes embeddings)
            output_dimension: 256/512/1024/2048 (Matryoshka embeddings)
            truncation: Truncate over-length inputs (default: True)

        Returns:
            LLMResponse with embeddings in content field
        """
        if not texts:
            raise ValueError("'texts' parameter required for embed operation")

        if model not in self.EMBEDDING_MODELS:
            raise ValueError(
                f"Invalid embedding model '{model}'. "
                f"Supported: {', '.join(self.EMBEDDING_MODELS)}"
            )

        # Ensure texts is a list
        if isinstance(texts, str):
            texts = [texts]

        try:
            client = self._get_client()

            # Build embed parameters
            embed_params = {
                "texts": texts,
                "model": model,
                "truncation": truncation
            }

            # Add optional parameters
            if input_type:
                embed_params["input_type"] = input_type

            if output_dimension:
                embed_params["output_dimension"] = output_dimension

            # Call VoyageAI API (synchronous)
            result = client.embed(**embed_params)

            # Extract embeddings
            embeddings = result.embeddings if hasattr(result, 'embeddings') else result

            # Calculate token count (from usage if available, else estimate)
            if hasattr(result, 'usage') and hasattr(result.usage, 'total_tokens'):
                total_tokens = result.usage.total_tokens
            else:
                # Estimate: ~1 token per 4 characters
                total_tokens = sum(len(text) for text in texts) // 4

            # Calculate cost
            cost_usd = self._calculate_embedding_cost(model, total_tokens)

            logger.info(
                "voyageai_embed_success",
                model=model,
                num_texts=len(texts),
                dimensions=len(embeddings[0]) if embeddings else 0,
                tokens=total_tokens,
                cost_usd=cost_usd
            )

            return LLMResponse(
                content=embeddings,  # List of float arrays
                input_tokens=total_tokens,
                output_tokens=0,  # Embeddings don't generate tokens
                cost_usd=cost_usd,
                provider_metadata={
                    "dimensions": len(embeddings[0]) if embeddings else 0,
                    "num_embeddings": len(embeddings),
                    "input_type": input_type,
                    "truncation": truncation
                }
            )

        except Exception as e:
            logger.error(f"VoyageAI embed failed: {str(e)}", model=model)
            raise Exception(f"VoyageAI embedding failed: {str(e)}")

    async def _rerank(
        self,
        model: str,
        query: str = None,
        documents: List[str] = None,
        top_k: Optional[int] = None,
        **kwargs
    ) -> LLMResponse:
        """
        Rerank documents by relevance to query

        Args:
            model: Reranking model name
            query: Search query
            documents: List of documents to rank
            top_k: Return only top K results (default: all)

        Returns:
            LLMResponse with ranked results in content field
            Each result: {index, text, score}
        """
        if not query:
            raise ValueError("'query' parameter required for rerank operation")

        if not documents:
            raise ValueError("'documents' parameter required for rerank operation")

        if model not in self.RERANK_MODELS:
            raise ValueError(
                f"Invalid reranking model '{model}'. "
                f"Supported: {', '.join(self.RERANK_MODELS)}"
            )

        try:
            client = self._get_client()

            # Build rerank parameters
            rerank_params = {
                "query": query,
                "documents": documents,
                "model": model
            }

            if top_k is not None:
                rerank_params["top_k"] = top_k

            # Call VoyageAI API (synchronous)
            result = client.rerank(**rerank_params)

            # Extract ranked results
            if hasattr(result, 'results'):
                ranked_results = [
                    {
                        "index": item.index,
                        "text": item.document,
                        "score": item.relevance_score
                    }
                    for item in result.results
                ]
            else:
                # Fallback structure
                ranked_results = result

            # Calculate token count
            if hasattr(result, 'usage') and hasattr(result.usage, 'total_tokens'):
                total_tokens = result.usage.total_tokens
            else:
                # Estimate: query + all documents
                total_tokens = (len(query) + sum(len(doc) for doc in documents)) // 4

            # Calculate cost
            cost_usd = self._calculate_rerank_cost(model, total_tokens)

            logger.info(
                "voyageai_rerank_success",
                model=model,
                num_documents=len(documents),
                top_k=top_k,
                tokens=total_tokens,
                cost_usd=cost_usd
            )

            return LLMResponse(
                content=ranked_results,  # List of ranked documents
                input_tokens=total_tokens,
                output_tokens=0,  # Reranking doesn't generate tokens
                cost_usd=cost_usd,
                provider_metadata={
                    "num_results": len(ranked_results),
                    "top_k": top_k,
                    "query_length": len(query)
                }
            )

        except Exception as e:
            logger.error(f"VoyageAI rerank failed: {str(e)}", model=model)
            raise Exception(f"VoyageAI reranking failed: {str(e)}")

    def _calculate_embedding_cost(self, model: str, tokens: int) -> float:
        """Calculate cost for embedding operation"""
        # Pricing per 1M tokens
        pricing = {
            "voyage-3.5": 0.06,
            "voyage-3.5-lite": 0.02,
            "voyage-3-large": 0.18,
            "voyage-code-3": 0.18,
            "voyage-finance-2": 0.12,
            "voyage-law-2": 0.12,
        }

        rate = pricing.get(model, 0.06)  # Default to voyage-3.5 rate
        return round((tokens / 1_000_000) * rate, 6)

    def _calculate_rerank_cost(self, model: str, tokens: int) -> float:
        """Calculate cost for reranking operation"""
        # Pricing per 1M tokens
        pricing = {
            "rerank-2.5": 0.05,
            "rerank-2.5-lite": 0.02,
        }

        rate = pricing.get(model, 0.02)  # Default to rerank-2.5-lite rate
        return round((tokens / 1_000_000) * rate, 6)


# Auto-register this provider
def register():
    from src.providers import ProviderRegistry
    ProviderRegistry.register(VoyageAIProvider)
