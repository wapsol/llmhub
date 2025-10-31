"""
API v2 Embeddings Operations Router
Vector embeddings generation for RAG and semantic search
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import time

from src.config.database import get_db
from src.models.database import APIClient
from src.models.schemas import (
    V2EmbeddingsRequest,
    V2EmbeddingsResponse
)
from src.services.auth import get_current_client
from src.services.embeddings_service import embeddings_service
from src.services.billing import billing_service
from src.utils.logger import logger

router = APIRouter()


def _select_embeddings_provider_and_model(
    request_provider: str = None,
    request_model: str = None
) -> tuple[str, str]:
    """
    Select embeddings provider and model based on user override or defaults

    Args:
        request_provider: Optional provider override ('openai' or 'cohere')
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
            "openai": "text-embedding-3-small",
            "cohere": "embed-english-v3.0"
        }
        return request_provider, provider_defaults.get(request_provider, "text-embedding-3-small")

    # If model only, infer provider
    if request_model:
        if "text-embedding" in request_model.lower() or "ada" in request_model.lower():
            return "openai", request_model
        elif "embed" in request_model.lower():
            return "cohere", request_model

    # Default: Cohere (better for RAG, multilingual support)
    available = embeddings_service.get_available_providers()
    if "cohere" in available:
        return "cohere", "embed-english-v3.0"
    elif "openai" in available:
        return "openai", "text-embedding-3-small"
    else:
        raise ValueError("No embeddings providers configured")


@router.post("/generate", response_model=V2EmbeddingsResponse)
async def generate_embeddings(
    request: V2EmbeddingsRequest,
    client: APIClient = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """
    Generate vector embeddings for RAG/semantic search

    Supports:
    - OpenAI: text-embedding-3-small, text-embedding-3-large, text-embedding-ada-002
    - Cohere: embed-english-v3.0, embed-multilingual-v3.0, embed-english-light-v3.0
    """
    start_time = time.time()

    try:
        # Select provider and model
        provider, model = _select_embeddings_provider_and_model(
            request.provider,
            request.embedding_model or request.model
        )

        # Generate embeddings
        response = await embeddings_service.generate_embeddings(
            texts=request.texts,
            provider=provider,
            model=model
        )

        generation_time_ms = int((time.time() - start_time) * 1000)

        # Log to database for billing
        # For embeddings, we only have total_tokens (no input/output split)
        log_id = billing_service.log_generation(
            db=db,
            client=client,
            endpoint="/api/v2/embeddings/generate",
            provider=provider,
            model=response.model,
            input_tokens=response.total_tokens,  # All tokens are "input" for embeddings
            output_tokens=0,  # No output tokens for embeddings
            input_cost_usd=response.cost_usd,
            output_cost_usd=0,
            generation_time_ms=generation_time_ms,
            success=True,
            request_metadata={
                "texts_count": len(request.texts),
                "dimensions": response.dimensions
            }
        )

        logger.info(
            "embeddings_api_success",
            client=client.client_name,
            provider=provider,
            model=response.model,
            texts_count=len(request.texts),
            dimensions=response.dimensions,
            cost_usd=response.cost_usd
        )

        return V2EmbeddingsResponse(
            success=True,
            content=response.embeddings,  # The actual embeddings vectors
            provider_used=provider,
            model_used=response.model,
            tokens_used=response.total_tokens,
            cost_usd=response.cost_usd,
            generation_time_ms=generation_time_ms,
            log_id=log_id,
            embeddings=response.embeddings,
            dimensions=response.dimensions
        )

    except ValueError as e:
        logger.error(f"Embeddings validation error: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail={
                "code": "VALIDATION_ERROR",
                "message": str(e)
            }
        )

    except Exception as e:
        generation_time_ms = int((time.time() - start_time) * 1000)
        logger.error(f"Embeddings generation failed: {str(e)}")

        # Log failed attempt
        try:
            billing_service.log_generation(
                db=db,
                client=client,
                endpoint="/api/v2/embeddings/generate",
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
                "code": "EMBEDDINGS_GENERATION_FAILED",
                "message": f"Failed to generate embeddings: {str(e)}"
            }
        )
