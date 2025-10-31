"""
API v2 Data Operations Router
Provider-agnostic embeddings and reranking endpoints
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import time
from typing import Union, List

from src.config.database import get_db
from src.models.database import APIClient
from src.models.schemas import (
    V2DataEmbedRequest,
    V2DataEmbedResponse,
    V2DataRerankRequest,
    V2DataRerankResponse
)
from src.services.auth import get_current_client
from src.services.llm_core import llm_core
from src.services.billing import billing_service
from src.utils.logger import logger

router = APIRouter()


def _select_embedding_provider_and_model(
    request_provider: str = None,
    request_model: str = None
) -> tuple[str, str]:
    """
    Select embedding provider and model

    Args:
        request_provider: Optional provider override
        request_model: Optional model override

    Returns:
        Tuple of (provider, model)
    """
    # If both specified, use them
    if request_provider and request_model:
        return request_provider, request_model

    # If provider only, use default model for that provider
    if request_provider:
        provider_defaults = {
            "voyageai": "voyage-3.5-lite",  # Best cost/performance
            "openai": "text-embedding-3-small",  # Future provider
            "cohere": "embed-english-v3.0"  # Future provider
        }
        return request_provider, provider_defaults.get(request_provider, "voyage-3.5-lite")

    # Default: Try VoyageAI first (best quality), fallback to others
    available = llm_core.get_available_providers()

    if "voyageai" in available:
        return "voyageai", "voyage-3.5-lite"  # Best cost/performance
    elif "cohere" in available:
        return "cohere", "embed-english-v3.0"
    elif "openai" in available:
        return "openai", "text-embedding-3-small"
    else:
        raise ValueError(
            "No embedding providers configured. "
            "Set VOYAGE_API_KEY, COHERE_API_KEY, or OPENAI_API_KEY in .env"
        )


def _select_rerank_provider_and_model(
    request_provider: str = None,
    request_model: str = None
) -> tuple[str, str]:
    """
    Select reranking provider and model

    Args:
        request_provider: Optional provider override
        request_model: Optional model override

    Returns:
        Tuple of (provider, model)
    """
    # If both specified, use them
    if request_provider and request_model:
        return request_provider, request_model

    # If provider only, use default model for that provider
    if request_provider:
        provider_defaults = {
            "voyageai": "rerank-2.5-lite",  # Fast and cheap
            "cohere": "rerank-english-v3.0"  # Future provider
        }
        return request_provider, provider_defaults.get(request_provider, "rerank-2.5-lite")

    # Default: VoyageAI (currently only reranking provider)
    available = llm_core.get_available_providers()

    if "voyageai" in available:
        return "voyageai", "rerank-2.5-lite"
    elif "cohere" in available:
        return "cohere", "rerank-english-v3.0"
    else:
        raise ValueError(
            "No reranking providers configured. "
            "Set VOYAGE_API_KEY or COHERE_API_KEY in .env"
        )


@router.post("/embed", response_model=V2DataEmbedResponse)
async def generate_embeddings(
    request: V2DataEmbedRequest,
    client: APIClient = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """
    Generate semantic embeddings for text(s)

    Embeddings convert text into high-dimensional vectors for:
    - Semantic search: Find similar documents
    - RAG: Retrieve relevant context for LLMs
    - Clustering: Group similar content
    - Recommendation: Find related items

    Supported providers:
    - VoyageAI: Premium quality with 6 models (general + domain-specific)
    - OpenAI: Cost-effective option (future integration)
    - Cohere: Multilingual support (future integration)

    Key features:
    - Asymmetric embeddings: Optimize for document vs query
    - Matryoshka embeddings: Flexible dimensions (256-2048)
    - Batch processing: Up to 1000 texts per request
    - Domain specialization: Code, finance, law models
    """
    start_time = time.time()

    try:
        # Select provider and model
        provider, model = _select_embedding_provider_and_model(
            request.provider,
            request.model
        )

        # Normalize texts to list
        if isinstance(request.texts, str):
            texts = [request.texts]
        else:
            texts = request.texts

        # Prepare kwargs for embedding provider
        embed_kwargs = {
            "texts": texts,
            "input_type": request.input_type,
            "output_dimension": request.output_dimension,
            "truncation": request.truncation,
            "operation": "embed"  # Signal to provider this is embedding operation
        }

        # Call embedding provider
        result = await llm_core.call_llm(
            provider=provider,
            model=model,
            messages=[{"role": "user", "content": str(texts)}],  # Not used by embeddings
            max_tokens=None,  # Not applicable for embeddings
            temperature=None,  # Not applicable for embeddings
            **embed_kwargs
        )

        generation_time_ms = int((time.time() - start_time) * 1000)

        # Extract embeddings and metadata
        embeddings = result["content"]  # List of float arrays
        dimensions = len(embeddings[0]) if embeddings else 0
        num_embeddings = len(embeddings)

        # Log to database for billing
        log_id = billing_service.log_generation(
            db=db,
            client=client,
            endpoint="/api/v2/data/embed",
            provider=provider,
            model=model,
            input_tokens=result["input_tokens"],
            output_tokens=result["output_tokens"],
            input_cost_usd=result["cost_usd"],
            output_cost_usd=0,
            generation_time_ms=generation_time_ms,
            success=True,
            request_metadata={
                "num_texts": len(texts),
                "input_type": request.input_type,
                "output_dimension": request.output_dimension,
                "truncation": request.truncation
            }
        )

        logger.info(
            "embedding_success",
            client=client.client_name,
            provider=provider,
            model=model,
            num_texts=len(texts),
            dimensions=dimensions,
            cost_usd=result["cost_usd"]
        )

        return V2DataEmbedResponse(
            success=True,
            content=embeddings,  # Keep for backward compatibility
            embeddings=embeddings,
            dimensions=dimensions,
            num_embeddings=num_embeddings,
            provider_used=provider,
            model_used=model,
            tokens_used=result["input_tokens"],
            cost_usd=result["cost_usd"],
            generation_time_ms=generation_time_ms,
            log_id=log_id
        )

    except ValueError as e:
        logger.error(f"Embedding validation error: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail={
                "code": "VALIDATION_ERROR",
                "message": str(e)
            }
        )

    except Exception as e:
        generation_time_ms = int((time.time() - start_time) * 1000)
        logger.error(f"Embedding generation failed: {str(e)}")

        # Log failed attempt
        try:
            billing_service.log_generation(
                db=db,
                client=client,
                endpoint="/api/v2/data/embed",
                provider=provider if 'provider' in locals() else "unknown",
                model=model if 'model' in locals() else "unknown",
                input_tokens=0,
                output_tokens=0,
                input_cost_usd=0,
                output_cost_usd=0,
                generation_time_ms=generation_time_ms,
                success=False,
                error_message=str(e),
                error_type=type(e).__name__
            )
        except:
            pass

        raise HTTPException(
            status_code=500,
            detail={
                "code": "EMBEDDING_GENERATION_FAILED",
                "message": f"Failed to generate embeddings: {str(e)}"
            }
        )


@router.post("/rerank", response_model=V2DataRerankResponse)
async def rerank_documents(
    request: V2DataRerankRequest,
    client: APIClient = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """
    Rerank documents by relevance to a query

    Reranking is a second-stage refinement for search results:
    1. **First stage**: Embedding-based search (fast, ~1000 docs → top 100)
    2. **Second stage**: Reranker (accurate, top 100 → best 10)

    Why rerank?
    - Embeddings provide fast approximate search
    - Rerankers jointly process query+document for precise scoring
    - Typical improvement: 15-30% accuracy boost

    Workflow:
    1. Use embeddings to retrieve ~100 candidates
    2. Use reranker to refine to top 10-20 most relevant
    3. Present refined results to user or LLM

    Supported providers:
    - VoyageAI: 2 models (rerank-2.5, rerank-2.5-lite)
    - Cohere: English and multilingual (future integration)
    """
    start_time = time.time()

    try:
        # Select provider and model
        provider, model = _select_rerank_provider_and_model(
            request.provider,
            request.model
        )

        # Prepare kwargs for reranking provider
        rerank_kwargs = {
            "query": request.query,
            "documents": request.documents,
            "top_k": request.top_k,
            "operation": "rerank"  # Signal to provider this is reranking operation
        }

        # Call reranking provider
        result = await llm_core.call_llm(
            provider=provider,
            model=model,
            messages=[{"role": "user", "content": request.query}],  # Not used by reranking
            max_tokens=None,  # Not applicable for reranking
            temperature=None,  # Not applicable for reranking
            **rerank_kwargs
        )

        generation_time_ms = int((time.time() - start_time) * 1000)

        # Extract ranked results
        ranked_results = result["content"]  # List of {index, text, score}
        num_results = len(ranked_results)

        # Log to database for billing
        log_id = billing_service.log_generation(
            db=db,
            client=client,
            endpoint="/api/v2/data/rerank",
            provider=provider,
            model=model,
            input_tokens=result["input_tokens"],
            output_tokens=result["output_tokens"],
            input_cost_usd=result["cost_usd"],
            output_cost_usd=0,
            generation_time_ms=generation_time_ms,
            success=True,
            request_metadata={
                "query_length": len(request.query),
                "num_documents": len(request.documents),
                "top_k": request.top_k,
                "num_results": num_results
            }
        )

        logger.info(
            "reranking_success",
            client=client.client_name,
            provider=provider,
            model=model,
            num_documents=len(request.documents),
            num_results=num_results,
            cost_usd=result["cost_usd"]
        )

        return V2DataRerankResponse(
            success=True,
            content=ranked_results,  # Keep for backward compatibility
            results=ranked_results,
            num_results=num_results,
            provider_used=provider,
            model_used=model,
            tokens_used=result["input_tokens"],
            cost_usd=result["cost_usd"],
            generation_time_ms=generation_time_ms,
            log_id=log_id
        )

    except ValueError as e:
        logger.error(f"Reranking validation error: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail={
                "code": "VALIDATION_ERROR",
                "message": str(e)
            }
        )

    except Exception as e:
        generation_time_ms = int((time.time() - start_time) * 1000)
        logger.error(f"Reranking failed: {str(e)}")

        # Log failed attempt
        try:
            billing_service.log_generation(
                db=db,
                client=client,
                endpoint="/api/v2/data/rerank",
                provider=provider if 'provider' in locals() else "unknown",
                model=model if 'model' in locals() else "unknown",
                input_tokens=0,
                output_tokens=0,
                input_cost_usd=0,
                output_cost_usd=0,
                generation_time_ms=generation_time_ms,
                success=False,
                error_message=str(e),
                error_type=type(e).__name__
            )
        except:
            pass

        raise HTTPException(
            status_code=500,
            detail={
                "code": "RERANKING_FAILED",
                "message": f"Failed to rerank documents: {str(e)}"
            }
        )
