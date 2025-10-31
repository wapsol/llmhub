"""
API v2 Audio Operations Router
Provider and model agnostic audio processing endpoints
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import time

from src.config.database import get_db
from src.models.database import APIClient
from src.models.schemas import (
    V2AudioTranscribeRequest,
    V2AudioTranscribeResponse,
    V2AudioSynthesizeRequest,
    V2BaseResponse
)
from src.services.auth import get_current_client
from src.services.llm_core import llm_core
from src.services.billing import billing_service
from src.utils.logger import logger

router = APIRouter()


def _select_transcription_provider_and_model(
    request_provider: str = None,
    request_model: str = None
) -> tuple[str, str]:
    """
    Select transcription provider and model

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
            "deepgram": "nova-3",
            "assemblyai": "best",
            "openai": "whisper-1"
        }
        return request_provider, provider_defaults.get(request_provider, "nova-3")

    # Default priority: Deepgram (fastest) → AssemblyAI (most features) → OpenAI (basic)
    available = llm_core.get_available_providers()
    if "deepgram" in available:
        return "deepgram", "nova-3"
    elif "assemblyai" in available:
        return "assemblyai", "best"
    elif "openai" in available:  # Whisper
        return "openai", "whisper-1"
    else:
        raise ValueError(
            "No transcription providers configured. "
            "Set DEEPGRAM_API_KEY, ASSEMBLYAI_API_KEY or OPENAI_API_KEY in .env"
        )


def _select_tts_provider_and_model(
    request_provider: str = None,
    request_model: str = None
) -> tuple[str, str]:
    """
    Select text-to-speech provider and model

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
            "elevenlabs": "eleven_flash_v2_5",
            "openai": "tts-1",  # Future provider
            "google": "en-US-Neural2-A"  # Future provider
        }
        return request_provider, provider_defaults.get(request_provider, "eleven_flash_v2_5")

    # Default: ElevenLabs (best quality)
    available = llm_core.get_available_providers()
    if "elevenlabs" in available:
        return "elevenlabs", "eleven_flash_v2_5"
    else:
        raise ValueError(
            "No text-to-speech providers configured. "
            "Set ELEVENLABS_API_KEY in .env"
        )


@router.post("/transcribe", response_model=V2AudioTranscribeResponse)
async def transcribe_audio(
    request: V2AudioTranscribeRequest,
    client: APIClient = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """
    Transcribe audio to text with audio intelligence

    Supported providers:
    - Deepgram (default): Ultra-fast with sub-200ms latency
      - Nova-3: 54% lower WER, real-time code-switching (10 languages)
      - Smart formatting, speaker diarization (40x faster)
      - Summarization, topics, sentiment, intents
      - Keyword boosting, PII redaction
      - All features included in base price ($0.258/hour)
    - AssemblyAI: State-of-the-art with Universal-2 (24% better proper nouns)
      - Speaker diarization, sentiment analysis
      - Entity detection, auto chapters & summarization
      - Topic classification (600+ IAB categories)
      - Content moderation
    - OpenAI Whisper: Cost-effective option (future integration)
    """
    start_time = time.time()

    try:
        # Select provider and model
        provider, model = _select_transcription_provider_and_model(
            request.provider,
            request.model if request.model else None
        )

        # Prepare kwargs for transcription provider
        transcribe_kwargs = {
            "audio_url": request.audio_url,
            "model": model,
            "language_code": request.language_code,

            # AssemblyAI-specific features
            "speaker_labels": request.speaker_labels,
            "speakers_expected": request.speakers_expected,
            "sentiment_analysis": request.sentiment_analysis,
            "entity_detection": request.entity_detection,
            "auto_chapters": request.auto_chapters,
            "summarization": request.summarization,
            "summarization_type": request.summarization_type,
            "iab_categories": request.iab_categories,
            "content_safety": request.content_safety,
            "filter_profanity": request.filter_profanity,
            "redact_pii": request.redact_pii,
            "word_boost": request.word_boost,
            "boost_param": request.boost_param,

            # Deepgram-specific features
            "detect_language": request.detect_language,
            "smart_format": request.smart_format,
            "punctuate": request.punctuate,
            "paragraphs": request.paragraphs,
            "numerals": request.numerals,
            "filler_words": request.filler_words,
            "utterances": request.utterances,
            "topics": request.topics,
            "custom_topics": request.custom_topics,
            "intents": request.intents,
            "keywords": request.keywords,
            "keyword_boost": request.keyword_boost,
            "search": request.search,
            "replace": request.replace,
            "multichannel": request.multichannel,

            "operation": "transcribe"  # Signal to provider this is transcription
        }

        # Call transcription provider
        result = await llm_core.call_llm(
            provider=provider,
            model=model,
            messages=[{"role": "user", "content": request.audio_url}],  # Not used by transcription
            max_tokens=None,  # Not applicable for transcription
            temperature=None,  # Not applicable for transcription
            **transcribe_kwargs
        )

        generation_time_ms = int((time.time() - start_time) * 1000)

        # Extract response content (dict with transcript and intelligence results)
        response_content = result["content"]

        # Log to database for billing
        log_id = billing_service.log_generation(
            db=db,
            client=client,
            endpoint="/api/v2/audio/transcribe",
            provider=provider,
            model=model,
            input_tokens=result["input_tokens"],  # Duration-based pseudo-tokens
            output_tokens=result["output_tokens"],
            input_cost_usd=result["cost_usd"],
            output_cost_usd=0,
            generation_time_ms=generation_time_ms,
            success=True,
            request_metadata={
                "audio_url": request.audio_url,
                "audio_duration": response_content.get("audio_duration"),
                "language_code": request.language_code,
                "features_enabled": {
                    # AssemblyAI features
                    "speaker_labels": request.speaker_labels,
                    "sentiment_analysis": request.sentiment_analysis,
                    "entity_detection": request.entity_detection,
                    "auto_chapters": request.auto_chapters,
                    "summarization": request.summarization,
                    "iab_categories": request.iab_categories,
                    "content_safety": request.content_safety,
                    # Deepgram features
                    "detect_language": request.detect_language,
                    "smart_format": request.smart_format,
                    "diarize": request.speaker_labels or request.utterances,
                    "topics": request.topics,
                    "intents": request.intents,
                    "keywords": bool(request.keywords)
                }
            }
        )

        logger.info(
            "transcription_success",
            client=client.client_name,
            provider=provider,
            model=model,
            audio_duration=response_content.get("audio_duration"),
            cost_usd=result["cost_usd"]
        )

        # Return comprehensive transcription response
        return V2AudioTranscribeResponse(
            success=True,
            content=response_content,  # Keep for backward compatibility
            text=response_content.get("text", ""),
            audio_duration=response_content.get("audio_duration", 0),
            confidence=response_content.get("confidence"),
            language_code=response_content.get("language_code"),
            utterances=response_content.get("utterances"),
            chapters=response_content.get("chapters"),
            entities=response_content.get("entities"),
            sentiment_analysis_results=response_content.get("sentiment_analysis_results"),
            iab_categories_result=response_content.get("iab_categories_result"),
            content_safety_labels=response_content.get("content_safety_labels"),
            summary=response_content.get("summary"),
            words=response_content.get("words"),
            provider_used=provider,
            model_used=model,
            tokens_used=result["input_tokens"],
            cost_usd=result["cost_usd"],
            generation_time_ms=generation_time_ms,
            log_id=log_id
        )

    except ValueError as e:
        logger.error(f"Transcription validation error: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail={
                "code": "VALIDATION_ERROR",
                "message": str(e)
            }
        )

    except Exception as e:
        generation_time_ms = int((time.time() - start_time) * 1000)
        logger.error(f"Transcription failed: {str(e)}")

        # Log failed attempt
        try:
            billing_service.log_generation(
                db=db,
                client=client,
                endpoint="/api/v2/audio/transcribe",
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
                "code": "TRANSCRIPTION_FAILED",
                "message": f"Failed to transcribe audio: {str(e)}"
            }
        )


@router.post("/synthesize", response_model=V2BaseResponse)
async def synthesize_audio(
    request: V2AudioSynthesizeRequest,
    client: APIClient = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """
    Generate speech from text (text-to-speech/TTS)

    Supported providers:
    - ElevenLabs: Premium quality with 6 models, voice cloning, 32 languages
    - OpenAI TTS: Cost-effective option (future integration)
    - Google Cloud TTS: High-quality multilingual (future integration)
    """
    start_time = time.time()

    try:
        # Select provider and model
        provider, model = _select_tts_provider_and_model(
            request.provider,
            request.model
        )

        # Prepare kwargs for TTS provider
        tts_kwargs = {
            "text": request.text,
            "voice": request.voice_id if request.voice_id else request.voice,
            "output_format": request.output_format,
            "language": request.language,
            "speed": request.speed
        }

        # Add ElevenLabs-specific voice settings if provided
        if request.stability is not None:
            tts_kwargs["stability"] = request.stability
        if request.similarity_boost is not None:
            tts_kwargs["similarity_boost"] = request.similarity_boost
        if request.style is not None:
            tts_kwargs["style"] = request.style
        if request.use_speaker_boost is not None:
            tts_kwargs["use_speaker_boost"] = request.use_speaker_boost

        # Call TTS provider
        # Note: messages parameter not used for TTS, using kwargs instead
        result = await llm_core.call_llm(
            provider=provider,
            model=model,
            messages=[{"role": "user", "content": request.text}],  # Not used by TTS
            max_tokens=None,  # Not applicable for TTS
            temperature=None,  # Not applicable for TTS
            **tts_kwargs
        )

        generation_time_ms = int((time.time() - start_time) * 1000)

        # Log to database for billing
        log_id = billing_service.log_generation(
            db=db,
            client=client,
            endpoint="/api/v2/audio/synthesize",
            provider=provider,
            model=model,
            input_tokens=result["input_tokens"],  # Character count * 100
            output_tokens=result["output_tokens"],
            input_cost_usd=result["cost_usd"],
            output_cost_usd=0,
            generation_time_ms=generation_time_ms,
            success=True,
            request_metadata={
                "text_length": len(request.text),
                "voice": request.voice_id or request.voice,
                "output_format": request.output_format,
                "language": request.language
            }
        )

        logger.info(
            "tts_synthesis_success",
            client=client.client_name,
            provider=provider,
            model=model,
            text_length=len(request.text),
            cost_usd=result["cost_usd"]
        )

        # Return base64-encoded audio data
        # Client can decode and save/stream as needed
        return V2BaseResponse(
            success=True,
            content=result["content"],  # Base64-encoded audio
            provider_used=provider,
            model_used=model,
            tokens_used=result["input_tokens"],
            cost_usd=result["cost_usd"],
            generation_time_ms=generation_time_ms,
            log_id=log_id
        )

    except ValueError as e:
        logger.error(f"TTS validation error: {str(e)}")
        raise HTTPException(
            status_code=400,
            detail={
                "code": "VALIDATION_ERROR",
                "message": str(e)
            }
        )

    except Exception as e:
        generation_time_ms = int((time.time() - start_time) * 1000)
        logger.error(f"TTS synthesis failed: {str(e)}")

        # Log failed attempt
        try:
            billing_service.log_generation(
                db=db,
                client=client,
                endpoint="/api/v2/audio/synthesize",
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
                "code": "TTS_SYNTHESIS_FAILED",
                "message": f"Failed to synthesize speech: {str(e)}"
            }
        )


@router.post("/separate", response_model=V2BaseResponse)
async def separate_audio(
    client: APIClient = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """Separate audio tracks/sources (isolate vocals, etc.)"""
    raise HTTPException(
        status_code=501,
        detail={
            "code": "NOT_IMPLEMENTED",
            "message": "Audio separation requires specialized audio processing libraries (Spleeter, Demucs).",
            "providers_needed": ["spleeter", "demucs"]
        }
    )


@router.post("/enhance", response_model=V2BaseResponse)
async def enhance_audio(
    client: APIClient = Depends(get_current_client),
    db: Session = Depends(get_db)
):
    """Enhance audio quality (denoise, normalize, etc.)"""
    raise HTTPException(
        status_code=501,
        detail={
            "code": "NOT_IMPLEMENTED",
            "message": "Audio enhancement requires audio processing libraries or services.",
            "providers_needed": ["audio_processing_service"]
        }
    )
