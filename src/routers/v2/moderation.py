"""
API v2 Moderation Operations Router
Content safety and moderation endpoints
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from src.config.database import get_db
from src.models.database import APIClient
from src.models.schemas import (
    V2ModerationRequest,
    V2DetectionRequest,
    V2PerspectiveAnalyzeRequest,
    V2PerspectiveAnalyzeResponse,
    V2BaseResponse
)
from src.services.auth import get_current_client
from src.routers.v2.text import _select_provider_and_model, _call_llm_with_prompt
from src.services.llm_core import llm_core
from src.services.billing import billing_service
from src.utils.logger import logger
import time

router = APIRouter()


@router.post("/moderate", response_model=V2BaseResponse)
async def moderate_content(
    request: V2ModerationRequest,
    client: APIClient = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """Check content for safety/policy violations"""
    # For text content, we can use LLM-based moderation as a fallback
    # Ideally this should use OpenAI Moderation API or similar specialized service

    if request.content_type == "text":
        provider, model = _select_provider_and_model(request.provider, request.model, "analysis")

        prompt = f"""Analyze the following content for safety and policy violations.
Check for: hate speech, violence, sexual content, self-harm, harassment, dangerous content.

Provide a JSON response with:
- safe: boolean (true if safe, false if unsafe)
- categories: list of detected violation categories
- severity: low, medium, high
- explanation: brief explanation

Content to analyze:
{request.content}"""

        system_prompt = "You are a content moderation expert. Analyze content objectively for policy violations."

        result = await _call_llm_with_prompt(
            prompt=prompt,
            system_prompt=system_prompt,
            provider=provider,
            model=model,
            client=client,
            db=db,
            endpoint="/api/v2/moderation/moderate",
            max_tokens=request.max_tokens or 500,
            temperature=0.1,  # Very low temperature for consistent moderation
            request_metadata={
                "content_type": request.content_type,
                "content_length": len(request.content)
            }
        )

        return V2BaseResponse(success=True, **result)
    else:
        raise HTTPException(
            status_code=501,
            detail={
                "code": "NOT_IMPLEMENTED",
                "message": f"Moderation for content_type '{request.content_type}' requires specialized provider integration.",
                "providers_needed": ["openai_moderation", "hive_ai", "perspective_api"]
            }
        )


@router.post("/detect", response_model=V2BaseResponse)
async def detect_content_types(
    request: V2DetectionRequest,
    client: APIClient = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """Detect specific content types (PII, hate speech, etc.)"""
    provider, model = _select_provider_and_model(request.provider, request.model, "analysis")

    detection_types_str = ", ".join(request.detection_types)

    prompt = f"""Detect and extract the following types of content: {detection_types_str}

Provide a JSON response with:
- detected: boolean (true if any of the requested types were found)
- findings: dict with each detection type as key and findings as value
- confidence: low, medium, high

Content to analyze:
{request.content}"""

    system_prompt = "You are an expert at detecting and classifying specific content types in text."

    result = await _call_llm_with_prompt(
        prompt=prompt,
        system_prompt=system_prompt,
        provider=provider,
        model=model,
        client=client,
        db=db,
        endpoint="/api/v2/moderation/detect",
        max_tokens=request.max_tokens or 500,
        temperature=0.1,
        request_metadata={
            "detection_types": request.detection_types,
            "content_length": len(request.content)
        }
    )

    return V2BaseResponse(success=True, **result)


@router.post("/analyze-toxicity", response_model=V2PerspectiveAnalyzeResponse)
async def analyze_toxicity(
    request: V2PerspectiveAnalyzeRequest,
    client: APIClient = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """
    Analyze text for toxicity using Google Perspective API

    Fast, accurate ML-based toxicity detection with ~100ms response time.
    Much faster and more accurate than LLM-based moderation.

    Attributes:
    - TOXICITY: Overall toxicity likelihood
    - SEVERE_TOXICITY: Very hateful, aggressive, disrespectful comments
    - IDENTITY_ATTACK: Negative or hateful comments about identity/ethnicity
    - INSULT: Insulting, inflammatory, or negative comments
    - PROFANITY: Swear words, curse words, or other obscene language
    - THREAT: Describes an intention to inflict pain, injury, or violence
    """
    start_time = time.time()

    try:
        # Use Perspective provider
        provider = "perspective"
        model = "toxicity"

        # Default to TOXICITY if no attributes specified
        requested_attributes = request.requested_attributes or ["TOXICITY"]

        # Prepare kwargs for Perspective provider
        perspective_kwargs = {
            "text": request.text,
            "requested_attributes": requested_attributes,
            "languages": request.languages,
            "do_not_store": request.do_not_store,
            "span_annotations": request.span_annotations,
            "operation": "analyze"
        }

        # Call Perspective API
        result = await llm_core.call_llm(
            provider=provider,
            model=model,
            messages=[{"role": "user", "content": request.text}],  # Not used by Perspective
            max_tokens=None,
            temperature=None,
            **perspective_kwargs
        )

        generation_time_ms = int((time.time() - start_time) * 1000)

        # Extract response content
        response_content = result["content"]

        # Log to database for billing (even though it's free, track usage)
        log_id = billing_service.log_generation(
            db=db,
            client=client,
            endpoint="/api/v2/moderation/analyze-toxicity",
            provider=provider,
            model=model,
            input_tokens=result["input_tokens"],
            output_tokens=result["output_tokens"],
            input_cost_usd=result["cost_usd"],
            output_cost_usd=0,
            generation_time_ms=generation_time_ms,
            success=True,
            request_metadata={
                "text_length": len(request.text),
                "requested_attributes": requested_attributes,
                "languages": request.languages,
                "toxicity_score": response_content.get("toxicity_score")
            }
        )

        logger.info(
            "perspective_analysis_success",
            client=client.client_name,
            provider=provider,
            model=model,
            text_length=len(request.text),
            toxicity_score=response_content.get("toxicity_score"),
            cost_usd=result["cost_usd"]
        )

        # Return Perspective-specific response
        return V2PerspectiveAnalyzeResponse(
            success=True,
            content=response_content,
            attribute_scores=response_content.get("attribute_scores", {}),
            detected_languages=response_content.get("detected_languages"),
            is_toxic=response_content.get("is_toxic"),
            toxicity_level=response_content.get("toxicity_level"),
            toxicity_score=response_content.get("toxicity_score"),
            provider_used=provider,
            model_used=model,
            tokens_used=result["input_tokens"],
            cost_usd=result["cost_usd"],
            generation_time_ms=generation_time_ms,
            log_id=log_id
        )

    except ValueError as e:
        logger.error(f"Perspective analysis validation error: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail={
                "code": "VALIDATION_ERROR",
                "message": str(e)
            }
        )

    except Exception as e:
        generation_time_ms = int((time.time() - start_time) * 1000)
        logger.error(f"Perspective analysis failed: {str(e)}")

        # Log failed attempt
        try:
            billing_service.log_generation(
                db=db,
                client=client,
                endpoint="/api/v2/moderation/analyze-toxicity",
                provider="perspective",
                model="toxicity",
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
                "code": "PERSPECTIVE_ANALYSIS_FAILED",
                "message": f"Failed to analyze text for toxicity: {str(e)}"
            }
        )
