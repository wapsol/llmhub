"""
Image Generation Router
API endpoints for AI-powered image generation with DALL-E 3
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
from uuid import UUID
import time
import httpx
from io import BytesIO

from src.config.database import get_db
from src.config.settings import settings
from src.models.database import APIClient
from src.models.schemas import (
    ImageGenerationRequest,
    ImageGenerationResponse,
    ImageEditRequest
)
from src.services.auth import get_current_client
from src.services.billing import billing_service
from src.utils.logger import logger

# MinIO client for image storage
try:
    from minio import Minio
    from minio.error import S3Error

    minio_client = Minio(
        settings.MINIO_ENDPOINT,
        access_key=settings.MINIO_ACCESS_KEY,
        secret_key=settings.MINIO_SECRET_KEY,
        secure=settings.MINIO_USE_SSL
    )
    minio_available = True
except Exception as e:
    logger.warning(f"MinIO not available: {str(e)}")
    minio_available = False

# OpenAI client for DALL-E 3
try:
    from openai import OpenAI
    openai_client = OpenAI(api_key=settings.OPENAI_API_KEY) if settings.OPENAI_API_KEY else None
except Exception as e:
    logger.warning(f"OpenAI client initialization failed: {str(e)}")
    openai_client = None

router = APIRouter()


@router.post("/generate-image", response_model=ImageGenerationResponse)
async def generate_image(
    request: ImageGenerationRequest,
    client: APIClient = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """
    Generate images using DALL-E 3

    Requires X-API-Key header for authentication.
    Tracks usage and costs per API client.
    Uploads generated images to MinIO for permanent storage.

    Returns:
        Generated image URLs with cost tracking
    """
    if not openai_client:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "SERVICE_UNAVAILABLE",
                "message": "OpenAI API key not configured"
            }
        )

    start_time = time.time()

    try:
        logger.info(
            "image_generation_started",
            client=client.client_name,
            prompt=request.prompt[:100],
            size=request.size,
            quality=request.quality
        )

        # Call DALL-E 3
        response = openai_client.images.generate(
            model="dall-e-3",
            prompt=request.prompt,
            size=request.size,
            quality=request.quality,
            n=1,  # DALL-E 3 only supports n=1
            response_format="url"
        )

        generation_time_ms = int((time.time() - start_time) * 1000)

        # Get generated image URL
        image_url = response.data[0].url
        revised_prompt = response.data[0].revised_prompt

        # Calculate cost based on size and quality
        cost_usd = _calculate_dalle3_cost(request.size, request.quality)

        # Upload to MinIO if available
        permanent_url = None
        if minio_available and image_url:
            try:
                permanent_url = await _upload_to_minio(
                    image_url=image_url,
                    client_id=str(client.client_id),
                    prompt=request.prompt
                )
                logger.info(f"Image uploaded to MinIO: {permanent_url}")
            except Exception as e:
                logger.error(f"MinIO upload failed: {str(e)}")
                # Continue even if MinIO upload fails - we still have OpenAI URL

        # Log to database for billing
        log_id = billing_service.log_generation(
            db=db,
            client=client,
            endpoint="/generate-image",
            provider="openai",
            model="dall-e-3",
            input_tokens=0,  # Image generation doesn't use tokens
            output_tokens=0,
            input_cost_usd=cost_usd,
            output_cost_usd=0,
            generation_time_ms=generation_time_ms,
            success=True,
            request_metadata={
                "prompt": request.prompt,
                "revised_prompt": revised_prompt,
                "size": request.size,
                "quality": request.quality,
                "style": request.style
            },
            response_metadata={
                "openai_url": image_url,
                "permanent_url": permanent_url
            }
        )

        # Check budget alert
        budget_alert = billing_service.check_budget_alert(db, client)
        if budget_alert:
            logger.warning("budget_alert", **budget_alert)

        return ImageGenerationResponse(
            success=True,
            image_url=permanent_url if permanent_url else image_url,
            openai_url=image_url,
            permanent_url=permanent_url,
            revised_prompt=revised_prompt,
            cost_usd=cost_usd,
            generation_time_ms=generation_time_ms,
            size=request.size,
            quality=request.quality,
            log_id=log_id
        )

    except Exception as e:
        generation_time_ms = int((time.time() - start_time) * 1000)
        logger.error(f"Image generation failed: {str(e)}")

        # Log failed attempt to database
        try:
            cost_usd = _calculate_dalle3_cost(request.size, request.quality)
            billing_service.log_generation(
                db=db,
                client=client,
                endpoint="/generate-image",
                provider="openai",
                model="dall-e-3",
                input_tokens=0,
                output_tokens=0,
                input_cost_usd=cost_usd if "BILLING_FAILED" not in str(e) else 0,
                output_cost_usd=0,
                generation_time_ms=generation_time_ms,
                success=False,
                error_message=str(e),
                error_type=type(e).__name__,
                request_metadata={
                    "prompt": request.prompt,
                    "size": request.size,
                    "quality": request.quality
                }
            )
        except:
            pass  # Don't fail if billing logging fails

        raise HTTPException(
            status_code=500,
            detail={
                "code": "GENERATION_FAILED",
                "message": f"Image generation failed: {str(e)}"
            }
        )


@router.post("/edit-image")
async def edit_image(
    request: ImageEditRequest,
    client: APIClient = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """
    Edit images using DALL-E 2 (DALL-E 3 doesn't support edits)

    Requires X-API-Key header for authentication.
    """
    if not openai_client:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "SERVICE_UNAVAILABLE",
                "message": "OpenAI API key not configured"
            }
        )

    start_time = time.time()

    try:
        logger.info(
            "image_edit_started",
            client=client.client_name,
            prompt=request.prompt[:100]
        )

        # Download image from URL
        async with httpx.AsyncClient() as http_client:
            img_response = await http_client.get(request.image_url)
            img_response.raise_for_status()
            image_bytes = BytesIO(img_response.content)

        # Optional mask
        mask_bytes = None
        if request.mask_url:
            async with httpx.AsyncClient() as http_client:
                mask_response = await http_client.get(request.mask_url)
                mask_response.raise_for_status()
                mask_bytes = BytesIO(mask_response.content)

        # Call DALL-E 2 edit endpoint
        response = openai_client.images.edit(
            model="dall-e-2",
            image=image_bytes,
            mask=mask_bytes,
            prompt=request.prompt,
            n=1,
            size=request.size,
            response_format="url"
        )

        generation_time_ms = int((time.time() - start_time) * 1000)

        edited_url = response.data[0].url

        # Calculate cost (DALL-E 2 edit pricing)
        cost_map = {
            "256x256": 0.016,
            "512x512": 0.018,
            "1024x1024": 0.020
        }
        cost_usd = cost_map.get(request.size, 0.020)

        # Upload to MinIO if available
        permanent_url = None
        if minio_available and edited_url:
            try:
                permanent_url = await _upload_to_minio(
                    image_url=edited_url,
                    client_id=str(client.client_id),
                    prompt=f"EDIT: {request.prompt}"
                )
            except Exception as e:
                logger.error(f"MinIO upload failed: {str(e)}")

        # Log to database
        billing_service.log_generation(
            db=db,
            client=client,
            endpoint="/edit-image",
            provider="openai",
            model="dall-e-2",
            input_tokens=0,
            output_tokens=0,
            input_cost_usd=cost_usd,
            output_cost_usd=0,
            generation_time_ms=generation_time_ms,
            success=True,
            request_metadata={
                "prompt": request.prompt,
                "image_url": request.image_url,
                "mask_url": request.mask_url,
                "size": request.size
            }
        )

        return {
            "success": True,
            "image_url": permanent_url if permanent_url else edited_url,
            "openai_url": edited_url,
            "permanent_url": permanent_url,
            "cost_usd": cost_usd,
            "generation_time_ms": generation_time_ms
        }

    except Exception as e:
        logger.error(f"Image edit failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "code": "EDIT_FAILED",
                "message": f"Image edit failed: {str(e)}"
            }
        )


# Helper functions

def _calculate_dalle3_cost(size: str, quality: str) -> float:
    """
    Calculate DALL-E 3 cost based on size and quality

    Pricing as of 2024:
    - Standard quality: $0.040 (1024x1024), $0.080 (1024x1792 or 1792x1024)
    - HD quality: $0.080 (1024x1024), $0.120 (1024x1792 or 1792x1024)
    """
    cost_map = {
        ("1024x1024", "standard"): 0.040,
        ("1024x1792", "standard"): 0.080,
        ("1792x1024", "standard"): 0.080,
        ("1024x1024", "hd"): 0.080,
        ("1024x1792", "hd"): 0.120,
        ("1792x1024", "hd"): 0.120,
    }

    return cost_map.get((size, quality), 0.080)


async def _upload_to_minio(
    image_url: str,
    client_id: str,
    prompt: str
) -> Optional[str]:
    """
    Download image from OpenAI URL and upload to MinIO

    Returns:
        Permanent MinIO URL
    """
    if not minio_available:
        return None

    try:
        # Download image from OpenAI
        async with httpx.AsyncClient() as client:
            response = await client.get(image_url)
            response.raise_for_status()
            image_data = response.content

        # Generate object name
        import hashlib
        from datetime import datetime

        prompt_hash = hashlib.md5(prompt.encode()).hexdigest()[:8]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        object_name = f"ai-generated/{client_id}/{timestamp}_{prompt_hash}.png"

        # Ensure bucket exists
        bucket_name = settings.MINIO_BUCKET
        if not minio_client.bucket_exists(bucket_name):
            minio_client.make_bucket(bucket_name)
            logger.info(f"Created MinIO bucket: {bucket_name}")

        # Upload to MinIO
        minio_client.put_object(
            bucket_name,
            object_name,
            BytesIO(image_data),
            length=len(image_data),
            content_type="image/png",
            metadata={
                "x-amz-meta-client-id": client_id,
                "x-amz-meta-prompt": prompt[:200],
                "x-amz-meta-generated-at": datetime.now().isoformat()
            }
        )

        # Construct public URL
        protocol = "https" if settings.MINIO_USE_SSL else "http"
        permanent_url = f"{protocol}://{settings.MINIO_ENDPOINT}/{bucket_name}/{object_name}"

        return permanent_url

    except Exception as e:
        logger.error(f"MinIO upload error: {str(e)}")
        raise
