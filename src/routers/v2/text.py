"""
API v2 Text Operations Router
Provider and model agnostic text processing endpoints
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Dict, Any
import time

from src.config.database import get_db
from src.config.settings import settings
from src.models.database import APIClient
from src.models.schemas import (
    V2TextGenerateRequest,
    V2TextTranslateRequest,
    V2TextSummarizeRequest,
    V2TextRewriteRequest,
    V2TextExpandRequest,
    V2TextCondenseRequest,
    V2TextAnalyzeRequest,
    V2TextClassifyRequest,
    V2TextExtractRequest,
    V2TextCompareRequest,
    V2BaseResponse
)
from src.services.auth import get_current_client
from src.services.llm_core import llm_core
from src.services.billing import billing_service
from src.utils.logger import logger

router = APIRouter()


def _select_provider_and_model(
    request_provider: str = None,
    request_model: str = None,
    task_type: str = "general"
) -> tuple[str, str]:
    """
    Intelligently select provider and model based on task type and user override

    Args:
        request_provider: Optional provider override from request
        request_model: Optional model override from request
        task_type: Type of task (general, fast, quality, translation, etc.)

    Returns:
        Tuple of (provider, model)
    """
    # If user specified both, use them
    if request_provider and request_model:
        return request_provider, request_model

    # If user specified provider only, use default model for that provider
    if request_provider:
        provider_defaults = {
            "claude": "claude-3-5-sonnet-20241022",
            "openai": "gpt-4-turbo",
            "groq": "mixtral-8x7b-32768",
            "google": "gemini-1.5-pro",
            "mistral": "mistral-large",
            "ollama": "llama2"
        }
        return request_provider, provider_defaults.get(request_provider, "gpt-4-turbo")

    # Smart routing based on task type
    task_routing = {
        "fast": ("groq", "mixtral-8x7b-32768"),  # Fast inference
        "quality": ("claude", "claude-3-5-sonnet-20241022"),  # Best quality
        "translation": ("openai", "gpt-4-turbo"),  # Good at languages
        "analysis": ("claude", "claude-3-5-sonnet-20241022"),  # Best reasoning
        "general": (settings.DEFAULT_PROVIDER, settings.DEFAULT_MODEL)
    }

    provider, model = task_routing.get(task_type, task_routing["general"])

    # If user specified model only, infer provider
    if request_model:
        if "claude" in request_model.lower():
            return "claude", request_model
        elif "gpt" in request_model.lower():
            return "openai", request_model
        elif "mixtral" in request_model.lower() or "llama" in request_model.lower():
            return "groq", request_model
        elif "gemini" in request_model.lower():
            return "google", request_model
        elif "mistral" in request_model.lower():
            return "mistral", request_model
        else:
            return provider, request_model

    return provider, model


async def _call_llm_with_prompt(
    prompt: str,
    system_prompt: str,
    provider: str,
    model: str,
    client: APIClient,
    db: Session,
    endpoint: str,
    max_tokens: int = None,
    temperature: float = None,
    request_metadata: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Common helper to call LLM and handle billing

    Returns:
        Dict with content, provider_used, model_used, tokens_used, cost_usd, generation_time_ms, log_id
    """
    start_time = time.time()

    try:
        # Prepare messages
        messages = [{"role": "user", "content": prompt}]

        # Call LLM
        result = await llm_core.call_llm(
            provider=provider,
            model=model,
            messages=messages,
            max_tokens=max_tokens or settings.DEFAULT_MAX_TOKENS,
            temperature=temperature or settings.DEFAULT_TEMPERATURE,
            system_prompt=system_prompt
        )

        generation_time_ms = int((time.time() - start_time) * 1000)

        # Log to database for billing
        log_id = billing_service.log_generation(
            db=db,
            client=client,
            endpoint=endpoint,
            provider=provider,
            model=model,
            input_tokens=result["input_tokens"],
            output_tokens=result["output_tokens"],
            input_cost_usd=result["cost_usd"] * (result["input_tokens"] / (result["input_tokens"] + result["output_tokens"])) if result["input_tokens"] + result["output_tokens"] > 0 else 0,
            output_cost_usd=result["cost_usd"] * (result["output_tokens"] / (result["input_tokens"] + result["output_tokens"])) if result["input_tokens"] + result["output_tokens"] > 0 else 0,
            generation_time_ms=generation_time_ms,
            success=True,
            request_metadata=request_metadata or {}
        )

        return {
            "content": result["content"],
            "provider_used": provider,
            "model_used": model,
            "tokens_used": result["input_tokens"] + result["output_tokens"],
            "cost_usd": result["cost_usd"],
            "generation_time_ms": generation_time_ms,
            "log_id": log_id
        }

    except Exception as e:
        generation_time_ms = int((time.time() - start_time) * 1000)
        logger.error(f"LLM call failed: {str(e)}")

        # Log failed attempt
        try:
            billing_service.log_generation(
                db=db,
                client=client,
                endpoint=endpoint,
                provider=provider,
                model=model,
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
                "code": "LLM_CALL_FAILED",
                "message": f"Failed to call LLM: {str(e)}"
            }
        )


@router.post("/generate", response_model=V2BaseResponse)
async def generate_text(
    request: V2TextGenerateRequest,
    client: APIClient = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """Generate text content from prompt"""
    provider, model = _select_provider_and_model(request.provider, request.model, "general")

    system_prompt = request.system_prompt or "You are a helpful AI assistant that generates high-quality text content."

    result = await _call_llm_with_prompt(
        prompt=request.prompt,
        system_prompt=system_prompt,
        provider=provider,
        model=model,
        client=client,
        db=db,
        endpoint="/api/v2/text/generate",
        max_tokens=request.max_tokens,
        temperature=request.temperature,
        request_metadata={"prompt": request.prompt[:500]}
    )

    return V2BaseResponse(success=True, **result)


@router.post("/translate", response_model=V2BaseResponse)
async def translate_text(
    request: V2TextTranslateRequest,
    client: APIClient = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """Translate text between languages"""
    provider, model = _select_provider_and_model(request.provider, request.model, "translation")

    prompt = f"""Translate the following text from {request.source_language} to {request.target_language}.
Preserve the original meaning, tone, and formatting.

Text to translate:
{request.text}

Provide only the translation, no explanations."""

    system_prompt = f"You are an expert translator specializing in {request.source_language} to {request.target_language} translation."

    result = await _call_llm_with_prompt(
        prompt=prompt,
        system_prompt=system_prompt,
        provider=provider,
        model=model,
        client=client,
        db=db,
        endpoint="/api/v2/text/translate",
        max_tokens=request.max_tokens,
        temperature=request.temperature or 0.3,  # Lower temperature for translation
        request_metadata={
            "source_language": request.source_language,
            "target_language": request.target_language,
            "text_length": len(request.text)
        }
    )

    return V2BaseResponse(success=True, **result)


@router.post("/summarize", response_model=V2BaseResponse)
async def summarize_text(
    request: V2TextSummarizeRequest,
    client: APIClient = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """Summarize long text"""
    provider, model = _select_provider_and_model(request.provider, request.model, "quality")

    length_instructions = {
        "short": "Provide a brief 2-3 sentence summary.",
        "medium": "Provide a comprehensive paragraph summary.",
        "long": "Provide a detailed multi-paragraph summary covering all key points."
    }

    prompt = f"""Summarize the following text.
{length_instructions.get(request.summary_length, length_instructions["medium"])}

Text to summarize:
{request.text}"""

    system_prompt = "You are an expert at creating clear, concise summaries that capture the essence of the original text."

    result = await _call_llm_with_prompt(
        prompt=prompt,
        system_prompt=system_prompt,
        provider=provider,
        model=model,
        client=client,
        db=db,
        endpoint="/api/v2/text/summarize",
        max_tokens=request.max_tokens,
        temperature=request.temperature or 0.5,
        request_metadata={
            "summary_length": request.summary_length,
            "original_length": len(request.text)
        }
    )

    return V2BaseResponse(success=True, **result)


@router.post("/rewrite", response_model=V2BaseResponse)
async def rewrite_text(
    request: V2TextRewriteRequest,
    client: APIClient = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """Rewrite/paraphrase text"""
    provider, model = _select_provider_and_model(request.provider, request.model, "general")

    style_instruction = f" in a {request.style} style" if request.style else ""

    prompt = f"""Rewrite the following text{style_instruction}.
Preserve the original meaning but use different words and sentence structures.

Original text:
{request.text}

Provide only the rewritten text, no explanations."""

    system_prompt = "You are an expert writer skilled at rewriting and paraphrasing text while maintaining its original meaning."

    result = await _call_llm_with_prompt(
        prompt=prompt,
        system_prompt=system_prompt,
        provider=provider,
        model=model,
        client=client,
        db=db,
        endpoint="/api/v2/text/rewrite",
        max_tokens=request.max_tokens,
        temperature=request.temperature or 0.7,
        request_metadata={
            "style": request.style,
            "original_length": len(request.text)
        }
    )

    return V2BaseResponse(success=True, **result)


@router.post("/expand", response_model=V2BaseResponse)
async def expand_text(
    request: V2TextExpandRequest,
    client: APIClient = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """Expand brief text into detailed content"""
    provider, model = _select_provider_and_model(request.provider, request.model, "quality")

    length_instruction = f"\nTarget length: approximately {request.target_length} words." if request.target_length else ""

    prompt = f"""Expand the following brief text into detailed, comprehensive content.
Add relevant details, examples, and explanations while staying on topic.{length_instruction}

Brief text:
{request.text}"""

    system_prompt = "You are an expert writer skilled at expanding brief ideas into detailed, well-structured content."

    result = await _call_llm_with_prompt(
        prompt=prompt,
        system_prompt=system_prompt,
        provider=provider,
        model=model,
        client=client,
        db=db,
        endpoint="/api/v2/text/expand",
        max_tokens=request.max_tokens,
        temperature=request.temperature or 0.7,
        request_metadata={
            "target_length": request.target_length,
            "original_length": len(request.text)
        }
    )

    return V2BaseResponse(success=True, **result)


@router.post("/condense", response_model=V2BaseResponse)
async def condense_text(
    request: V2TextCondenseRequest,
    client: APIClient = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """Condense long text to key points"""
    provider, model = _select_provider_and_model(request.provider, request.model, "quality")

    prompt = f"""Condense the following text into {request.num_points} key points.
Present as a numbered list of the most important takeaways.

Text to condense:
{request.text}"""

    system_prompt = "You are an expert at identifying and articulating the most important points from lengthy text."

    result = await _call_llm_with_prompt(
        prompt=prompt,
        system_prompt=system_prompt,
        provider=provider,
        model=model,
        client=client,
        db=db,
        endpoint="/api/v2/text/condense",
        max_tokens=request.max_tokens,
        temperature=request.temperature or 0.5,
        request_metadata={
            "num_points": request.num_points,
            "original_length": len(request.text)
        }
    )

    return V2BaseResponse(success=True, **result)


@router.post("/analyze", response_model=V2BaseResponse)
async def analyze_text(
    request: V2TextAnalyzeRequest,
    client: APIClient = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """Analyze text (sentiment, tone, etc.)"""
    provider, model = _select_provider_and_model(request.provider, request.model, "analysis")

    analysis_types_str = ", ".join(request.analysis_types)

    prompt = f"""Analyze the following text for: {analysis_types_str}

Provide your analysis in JSON format with each analysis type as a key.

Text to analyze:
{request.text}"""

    system_prompt = "You are an expert text analyst skilled at identifying sentiment, tone, emotion, and other textual characteristics."

    result = await _call_llm_with_prompt(
        prompt=prompt,
        system_prompt=system_prompt,
        provider=provider,
        model=model,
        client=client,
        db=db,
        endpoint="/api/v2/text/analyze",
        max_tokens=request.max_tokens,
        temperature=request.temperature or 0.3,  # Lower temperature for analysis
        request_metadata={
            "analysis_types": request.analysis_types,
            "text_length": len(request.text)
        }
    )

    return V2BaseResponse(success=True, **result)


@router.post("/classify", response_model=V2BaseResponse)
async def classify_text(
    request: V2TextClassifyRequest,
    client: APIClient = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """Classify text into categories"""
    provider, model = _select_provider_and_model(request.provider, request.model, "analysis")

    categories_str = "\n- ".join(request.categories)

    prompt = f"""Classify the following text into one of these categories:
- {categories_str}

Text to classify:
{request.text}

Respond with ONLY the category name that best matches, nothing else."""

    system_prompt = "You are an expert at text classification and categorization."

    result = await _call_llm_with_prompt(
        prompt=prompt,
        system_prompt=system_prompt,
        provider=provider,
        model=model,
        client=client,
        db=db,
        endpoint="/api/v2/text/classify",
        max_tokens=request.max_tokens or 100,
        temperature=request.temperature or 0.1,  # Very low temperature for classification
        request_metadata={
            "categories": request.categories,
            "text_length": len(request.text)
        }
    )

    return V2BaseResponse(success=True, **result)


@router.post("/extract", response_model=V2BaseResponse)
async def extract_from_text(
    request: V2TextExtractRequest,
    client: APIClient = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """Extract entities, keywords, or structured data"""
    provider, model = _select_provider_and_model(request.provider, request.model, "analysis")

    extract_types_str = ", ".join(request.extract_types)

    prompt = f"""Extract the following from the text: {extract_types_str}

Provide the extracted information in JSON format with each extraction type as a key.

Text to extract from:
{request.text}"""

    system_prompt = "You are an expert at extracting structured information from unstructured text."

    result = await _call_llm_with_prompt(
        prompt=prompt,
        system_prompt=system_prompt,
        provider=provider,
        model=model,
        client=client,
        db=db,
        endpoint="/api/v2/text/extract",
        max_tokens=request.max_tokens,
        temperature=request.temperature or 0.3,
        request_metadata={
            "extract_types": request.extract_types,
            "text_length": len(request.text)
        }
    )

    return V2BaseResponse(success=True, **result)


@router.post("/compare", response_model=V2BaseResponse)
async def compare_texts(
    request: V2TextCompareRequest,
    client: APIClient = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """Compare multiple texts"""
    provider, model = _select_provider_and_model(request.provider, request.model, "analysis")

    # Format texts for comparison
    texts_formatted = "\n\n".join([f"Text {i+1}:\n{text}" for i, text in enumerate(request.texts)])

    aspects_instruction = ""
    if request.comparison_aspects:
        aspects_str = ", ".join(request.comparison_aspects)
        aspects_instruction = f"\nFocus on these aspects: {aspects_str}"

    prompt = f"""Compare the following texts and identify key differences and similarities.{aspects_instruction}

{texts_formatted}

Provide a structured comparison highlighting:
1. Key differences
2. Similarities
3. Notable patterns or themes"""

    system_prompt = "You are an expert at comparing and contrasting texts to identify patterns, differences, and similarities."

    result = await _call_llm_with_prompt(
        prompt=prompt,
        system_prompt=system_prompt,
        provider=provider,
        model=model,
        client=client,
        db=db,
        endpoint="/api/v2/text/compare",
        max_tokens=request.max_tokens,
        temperature=request.temperature or 0.5,
        request_metadata={
            "num_texts": len(request.texts),
            "comparison_aspects": request.comparison_aspects
        }
    )

    return V2BaseResponse(success=True, **result)
