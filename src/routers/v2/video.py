"""
API v2 Video Operations Router
Provider and model agnostic video processing endpoints
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import time

from src.config.database import get_db
from src.models.database import APIClient
from src.models.schemas import (
    V2VideoGenerateRequest,
    V2VideoRemixRequest,
    V2VideoExtendRequest,
    V2VideoInterpolateRequest,
    V2VideoDescribeRequest,
    V2BaseResponse
)
from src.services.auth import get_current_client
from src.services.llm_core import llm_core
from src.services.billing import billing_service
from src.utils.logger import logger

router = APIRouter()


def _select_video_provider_and_model(
    request_provider: str = None,
    request_model: str = None
) -> tuple[str, str]:
    """
    Select video generation provider and model

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
            "runway": "gen4_turbo",
            "pika": "pika-2.2-720p",
            "sora": "sora-1.0"  # Future provider
        }
        return request_provider, provider_defaults.get(request_provider, "gen4_turbo")

    # Default: Try Pika first (cheaper), then Runway, then error
    available = llm_core.get_available_providers()
    if "pika" in available:
        return "pika", "pika-2.2-720p"
    elif "runway" in available:
        return "runway", "gen4_turbo"
    else:
        raise ValueError(
            "No video generation providers configured. "
            "Set RUNWAY_API_KEY or FAL_KEY (for Pika) in .env"
        )


@router.post("/generate", response_model=V2BaseResponse)
async def generate_video(
    request: V2VideoGenerateRequest,
    client: APIClient = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """
    Generate video from text prompt and image

    Supported providers:
    - Pika Labs (via Fal.ai): v2.2 models, 720p ($0.20) or 1080p ($0.45) per 5s video
    - RunwayML: Gen-4 models, credit-based pricing

    Both require 'prompt_image' URL for image-to-video generation.

    Note: Pure text-to-video may require first generating an image,
    then converting to video.
    """
    start_time = time.time()

    try:
        # Select provider and model
        provider, model = _select_video_provider_and_model(
            request.provider,
            request.model
        )

        # Map aspect ratio to Runway format
        aspect_ratio_map = {
            "16:9": "1280:720",
            "9:16": "720:1280",
            "1:1": "1024:1024",
            "4:3": "1024:768"
        }
        ratio = aspect_ratio_map.get(request.aspect_ratio, "1280:720")

        # Both Runway and Pika need an image URL for image-to-video
        # This would typically be provided by the caller or generated first
        prompt_image = getattr(request, 'prompt_image', None)

        if not prompt_image:
            raise HTTPException(
                status_code=400,
                detail={
                    "code": "IMAGE_REQUIRED",
                    "message": f"{provider.title()} requires 'prompt_image' URL for video generation. "
                               "Please provide an image URL or generate one first using /api/v2/image/generate",
                    "solution": "Add 'prompt_image': 'https://your-image-url.jpg' to request"
                }
            )

        # Call video generation provider
        # Note: messages parameter not used for video, using kwargs instead
        result = await llm_core.call_llm(
            provider=provider,
            model=model,
            messages=[{"role": "user", "content": request.prompt}],  # Not used by Runway
            max_tokens=None,  # Not applicable for video
            temperature=None,  # Not applicable for video
            # Video-specific parameters passed via kwargs
            prompt=request.prompt,
            prompt_image=prompt_image,
            duration=request.duration,
            ratio=ratio,
            operation="generate"
        )

        generation_time_ms = int((time.time() - start_time) * 1000)

        # Log to database for billing
        log_id = billing_service.log_generation(
            db=db,
            client=client,
            endpoint="/api/v2/video/generate",
            provider=provider,
            model=model,
            input_tokens=result["input_tokens"],  # Duration-based proxy
            output_tokens=result["output_tokens"],
            input_cost_usd=result["cost_usd"],
            output_cost_usd=0,
            generation_time_ms=generation_time_ms,
            success=True,
            request_metadata={
                "prompt": request.prompt,
                "duration": request.duration,
                "aspect_ratio": request.aspect_ratio,
                "ratio": ratio
            }
        )

        logger.info(
            "video_generation_success",
            client=client.client_name,
            provider=provider,
            model=model,
            duration=request.duration,
            cost_usd=result["cost_usd"]
        )

        return V2BaseResponse(
            success=True,
            content=result["content"],  # Video URL
            provider_used=provider,
            model_used=model,
            tokens_used=result["input_tokens"],
            cost_usd=result["cost_usd"],
            generation_time_ms=generation_time_ms,
            log_id=log_id
        )

    except ValueError as e:
        logger.error(f"Video generation validation error: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail={
                "code": "VALIDATION_ERROR",
                "message": str(e)
            }
        )

    except Exception as e:
        generation_time_ms = int((time.time() - start_time) * 1000)
        logger.error(f"Video generation failed: {str(e)}")

        # Log failed attempt
        try:
            billing_service.log_generation(
                db=db,
                client=client,
                endpoint="/api/v2/video/generate",
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
                "code": "VIDEO_GENERATION_FAILED",
                "message": f"Failed to generate video: {str(e)}"
            }
        )


@router.post("/remix", response_model=V2BaseResponse)
async def remix_video(
    request: V2VideoRemixRequest,
    client: APIClient = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """
    Remix/edit existing video with AI

    Status: Placeholder - requires RunwayML video-to-video endpoint
    """
    raise HTTPException(
        status_code=501,
        detail={
            "code": "NOT_IMPLEMENTED",
            "message": "Video remixing requires RunwayML video-to-video endpoint support. "
                       "This feature will be implemented when the SDK adds video-to-video capabilities.",
            "providers_needed": ["runway_video_to_video"],
            "estimated_availability": "Q1 2026"
        }
    )


@router.post("/extend", response_model=V2BaseResponse)
async def extend_video(
    request: V2VideoExtendRequest,
    client: APIClient = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """
    Extend video duration by generating additional frames

    Status: Placeholder - requires RunwayML extend endpoint
    """
    raise HTTPException(
        status_code=501,
        detail={
            "code": "NOT_IMPLEMENTED",
            "message": "Video extension requires RunwayML extend endpoint support. "
                       "This feature will be implemented when the SDK adds extend capabilities.",
            "providers_needed": ["runway_extend"],
            "estimated_availability": "Q1 2026"
        }
    )


@router.post("/interpolate", response_model=V2BaseResponse)
async def interpolate_video(
    request: V2VideoInterpolateRequest,
    client: APIClient = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """
    Create smooth transitions between video frames (frame interpolation)

    Status: Placeholder - requires specialized video processing
    """
    raise HTTPException(
        status_code=501,
        detail={
            "code": "NOT_IMPLEMENTED",
            "message": "Frame interpolation requires specialized video processing tools.",
            "providers_needed": ["runway", "stability_video", "topaz"],
            "alternative": "Consider using external frame interpolation tools"
        }
    )


@router.post("/describe", response_model=V2BaseResponse)
async def describe_video(
    request: V2VideoDescribeRequest,
    client: APIClient = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """
    Generate description of video contents using vision models

    Status: Placeholder - requires GPT-4 Vision or Gemini Vision integration
    """
    raise HTTPException(
        status_code=501,
        detail={
            "code": "NOT_IMPLEMENTED",
            "message": "Video description requires vision model integration (GPT-4 Vision, Gemini Vision).",
            "providers_needed": ["openai_vision", "google_vision"],
            "alternative": "Use /api/v2/image/describe on video frames"
        }
    )
