"""
Content Generation Router
API endpoints for LLM-powered content generation
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any
from uuid import UUID

from src.config.database import get_db
from src.models.database import APIClient
from src.models.schemas import (
    ContentGenerationRequest,
    ContentGenerationResponse,
    TranslationRequest
)
from src.services.auth import get_current_client
from src.services.llm_core import llm_core
from src.services.billing import billing_service
from src.utils.logger import logger

router = APIRouter()


@router.post("/generate-content", response_model=ContentGenerationResponse)
async def generate_content(
    request: ContentGenerationRequest,
    client: APIClient = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """
    Generate multilingual content from a text prompt

    Requires X-API-Key header for authentication.
    Tracks usage and costs per API client.

    Returns:
        Generated content in requested languages with cost tracking
    """
    try:
        logger.info(
            "content_generation_started",
            client=client.client_name,
            provider=request.provider,
            model=request.model,
            languages=request.languages
        )

        # Prepare messages
        messages = [
            {"role": "user", "content": request.prompt}
        ]

        # Generate content for first language (primary)
        primary_language = request.languages[0] if request.languages else "en"

        # Call LLM
        result = await llm_core.call_llm(
            provider=request.provider.value,
            model=request.model,
            messages=messages,
            max_tokens=request.max_tokens,
            temperature=request.temperature
        )

        # Parse generated content (assume markdown format)
        content_dict = {
            primary_language: {
                "title": _extract_title(result["content"]),
                "body": result["content"],
                "meta_title": _extract_meta_title(result["content"]),
                "meta_description": _extract_meta_description(result["content"]),
                "meta_keywords": _extract_keywords(result["content"])
            }
        }

        # If multiple languages requested, translate
        if len(request.languages) > 1:
            for target_lang in request.languages[1:]:
                # TODO: Implement translation for other languages
                # For now, just copy the primary language content
                content_dict[target_lang] = content_dict[primary_language].copy()

        # Log to database for billing
        log_id = billing_service.log_generation(
            db=db,
            client=client,
            endpoint="/generate-content",
            provider=request.provider.value,
            model=request.model,
            input_tokens=result["input_tokens"],
            output_tokens=result["output_tokens"],
            input_cost_usd=result["cost_usd"] * (result["input_tokens"] / (result["input_tokens"] + result["output_tokens"])),
            output_cost_usd=result["cost_usd"] * (result["output_tokens"] / (result["input_tokens"] + result["output_tokens"])),
            generation_time_ms=result["generation_time_ms"],
            success=True,
            template_id=request.template_id,
            request_metadata={
                "prompt": request.prompt[:500],  # Store first 500 chars
                "languages": request.languages,
                "max_tokens": request.max_tokens,
                "temperature": request.temperature
            },
            response_metadata={
                "content_length": len(result["content"])
            }
        )

        # Check budget alert
        budget_alert = billing_service.check_budget_alert(db, client)
        if budget_alert:
            logger.warning("budget_alert", **budget_alert)

        return ContentGenerationResponse(
            success=True,
            content=content_dict,
            tokens_used=result["input_tokens"] + result["output_tokens"],
            cost_usd=result["cost_usd"],
            generation_time_ms=result["generation_time_ms"],
            provider=request.provider.value,
            model=request.model,
            log_id=log_id
        )

    except Exception as e:
        logger.error(f"Content generation failed: {str(e)}")

        # Log failed attempt to database
        try:
            billing_service.log_generation(
                db=db,
                client=client,
                endpoint="/generate-content",
                provider=request.provider.value,
                model=request.model,
                input_tokens=0,
                output_tokens=0,
                input_cost_usd=0,
                output_cost_usd=0,
                generation_time_ms=0,
                success=False,
                error_message=str(e),
                error_type=type(e).__name__
            )
        except:
            pass  # Don't fail if billing logging fails

        raise HTTPException(
            status_code=500,
            detail={
                "code": "GENERATION_FAILED",
                "message": f"Content generation failed: {str(e)}"
            }
        )


@router.post("/translate")
async def translate_content(
    request: TranslationRequest,
    client: APIClient = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """
    Translate content to target languages

    Preserves markdown formatting and structure.
    """
    try:
        logger.info(
            "translation_started",
            client=client.client_name,
            source_language=request.source_language,
            target_languages=request.target_languages
        )

        translations = {}

        for target_lang in request.target_languages:
            # Prepare translation prompt
            prompt = f"""Translate the following content from {request.source_language} to {target_lang}.
Preserve all markdown formatting, links, and structure.

Content to translate:
{request.content.model_dump_json()}

Return only the translated content in the same JSON structure."""

            messages = [{"role": "user", "content": prompt}]

            # Call LLM
            result = await llm_core.call_llm(
                provider=request.provider.value,
                model=request.model,
                messages=messages
            )

            # TODO: Parse JSON response properly
            # For now, store raw content
            translations[target_lang] = {
                "title": result["content"][:100],  # Placeholder
                "body": result["content"]
            }

            # Log to database
            billing_service.log_generation(
                db=db,
                client=client,
                endpoint="/translate",
                provider=request.provider.value,
                model=request.model,
                input_tokens=result["input_tokens"],
                output_tokens=result["output_tokens"],
                input_cost_usd=result["cost_usd"] * 0.5,
                output_cost_usd=result["cost_usd"] * 0.5,
                generation_time_ms=result["generation_time_ms"],
                success=True,
                request_metadata={
                    "source_language": request.source_language,
                    "target_language": target_lang
                }
            )

        return {
            "success": True,
            "translations": translations
        }

    except Exception as e:
        logger.error(f"Translation failed: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail={
                "code": "TRANSLATION_FAILED",
                "message": f"Translation failed: {str(e)}"
            }
        )


# Helper functions for content parsing
def _extract_title(content: str) -> str:
    """Extract title from markdown content"""
    lines = content.split("\n")
    for line in lines:
        if line.startswith("# "):
            return line[2:].strip()
    return "Untitled"


def _extract_meta_title(content: str) -> str:
    """Extract meta title (first H1 or truncated title)"""
    title = _extract_title(content)
    return title[:60] if len(title) > 60 else title


def _extract_meta_description(content: str) -> str:
    """Extract meta description (first paragraph or truncated)"""
    lines = content.split("\n")
    for line in lines:
        if line and not line.startswith("#") and len(line) > 20:
            return line[:160] if len(line) > 160 else line
    return ""


def _extract_keywords(content: str) -> str:
    """Extract keywords (simple implementation)"""
    # TODO: Implement proper keyword extraction
    title = _extract_title(content)
    words = title.split()[:5]
    return ", ".join(words)
