"""
AssemblyAI Provider - Speech-to-Text and Audio Intelligence
State-of-the-art transcription with speaker diarization, sentiment, and more
"""

from typing import Dict, Any, List, Optional
import time
import assemblyai as aai

from src.providers.base import BaseProvider, LLMResponse, ProviderConfig, ProviderMetadata
from src.utils.logger import logger


class AssemblyAIProvider(BaseProvider):
    """
    AssemblyAI speech-to-text and audio intelligence provider

    Supported models:
    - best (Universal-2): State-of-the-art accuracy, $0.37/hour
    - nano: Cost-effective transcription, $0.12/hour

    Audio Intelligence Features:
    - Speaker diarization (who said what)
    - Sentiment analysis (per sentence)
    - Entity detection (names, dates, organizations)
    - Auto chapters (topic segmentation)
    - Summarization (bullets, paragraph, headline)
    - Topic detection (IAB categories)
    - Content moderation
    - PII redaction
    - Custom vocabulary boosting

    Operations:
    - transcribe: Convert audio to text with intelligence features
    """

    # Model tiers
    MODELS = [
        "best",  # Universal-2 - most accurate ($0.37/hour)
        "nano",  # Budget option ($0.12/hour)
    ]

    # Add-on features with pricing per hour
    ADD_ON_PRICING = {
        "speaker_labels": 0.02,
        "sentiment_analysis": 0.02,
        "entity_detection": 0.08,
        "auto_chapters": 0.08,
        "summarization": 0.03,
        "iab_categories": 0.15,
        "content_safety_labels": 0.15,
    }

    @property
    def provider_name(self) -> str:
        return "assemblyai"

    def is_available(self) -> bool:
        """Check if AssemblyAI API key is configured"""
        return self.config.api_key is not None and len(self.config.api_key) > 0

    def get_models(self) -> List[str]:
        """Return supported model tiers"""
        return self.MODELS

    def get_metadata(self) -> ProviderMetadata:
        """Provider information for UI display"""
        return ProviderMetadata(
            display_name="AssemblyAI",
            description="State-of-the-art speech-to-text with Universal-2 model. "
                        "Includes speaker diarization, sentiment analysis, entity detection, "
                        "summarization, and content moderation.",
            logo_url="https://www.assemblyai.com/favicon.ico",
            website_url="https://www.assemblyai.com",
            requires_api_key=True,
            requires_base_url=False
        )

    def _get_client(self):
        """Lazy-load AssemblyAI client"""
        if self._client is None:
            try:
                # Set API key globally for AssemblyAI SDK
                aai.settings.api_key = self.config.api_key
                self._client = aai.Transcriber()
                logger.info(f"Initialized AssemblyAI client")
            except ImportError:
                raise ImportError(
                    "assemblyai package not installed. "
                    "Install with: pip install assemblyai"
                )
            except Exception as e:
                logger.error(f"Failed to initialize AssemblyAI client: {str(e)}")
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
        Route to transcription operation

        Operations:
        - transcribe: Convert audio to text (audio_url kwarg required)
        """
        if not self.is_available():
            raise ValueError(
                "AssemblyAI provider not configured. "
                "Set ASSEMBLYAI_API_KEY in .env"
            )

        operation = kwargs.get("operation", "transcribe")

        if operation == "transcribe":
            return await self._transcribe(**kwargs)
        else:
            raise ValueError(
                f"Unknown operation '{operation}'. "
                f"Supported: transcribe"
            )

    async def _transcribe(
        self,
        audio_url: str = None,
        model: str = "best",
        language_code: Optional[str] = None,
        speaker_labels: bool = False,
        speakers_expected: Optional[int] = None,
        sentiment_analysis: bool = False,
        entity_detection: bool = False,
        auto_chapters: bool = False,
        summarization: bool = False,
        summarization_type: str = "bullets",
        iab_categories: bool = False,
        content_safety: bool = False,
        filter_profanity: bool = False,
        redact_pii: bool = False,
        word_boost: Optional[List[str]] = None,
        boost_param: str = "default",
        **kwargs
    ) -> LLMResponse:
        """
        Transcribe audio with optional audio intelligence features

        Args:
            audio_url: Public URL to audio file (REQUIRED)
            model: "best" or "nano"
            language_code: Language hint (e.g., "en", "es")
            speaker_labels: Enable speaker diarization
            speakers_expected: Expected number of speakers
            sentiment_analysis: Sentiment per sentence
            entity_detection: Extract named entities
            auto_chapters: Generate chapters
            summarization: AI summary
            summarization_type: "bullets", "paragraph", or "headline"
            iab_categories: Topic classification
            content_safety: Content moderation
            filter_profanity: Bleep profanity
            redact_pii: Redact personal info
            word_boost: Custom vocabulary list
            boost_param: Boost level ("low", "default", "high")

        Returns:
            LLMResponse with transcript and audio intelligence results
        """
        if not audio_url:
            raise ValueError("'audio_url' parameter required for transcription")

        if model not in self.MODELS:
            raise ValueError(
                f"Invalid model '{model}'. "
                f"Supported: {', '.join(self.MODELS)}"
            )

        try:
            client = self._get_client()

            # Build transcription config
            config = aai.TranscriptionConfig(
                speech_model=aai.SpeechModel.best if model == "best" else aai.SpeechModel.nano,
                language_code=language_code if language_code else None,
                punctuate=True,
                format_text=True,

                # Speaker diarization
                speaker_labels=speaker_labels,
                speakers_expected=speakers_expected if speakers_expected else None,

                # Audio intelligence features
                sentiment_analysis=sentiment_analysis,
                entity_detection=entity_detection,
                auto_chapters=auto_chapters,
                iab_categories=iab_categories,
                content_safety_labels=content_safety if content_safety else None,

                # PII and profanity
                filter_profanity=filter_profanity,
                redact_pii=redact_pii,

                # Custom vocabulary
                word_boost=word_boost if word_boost else None,
                boost_param=boost_param if word_boost else None,
            )

            # Add summarization if requested
            if summarization:
                if summarization_type == "bullets":
                    config.summarization = True
                    config.summary_type = aai.SummarizationType.bullets
                elif summarization_type == "paragraph":
                    config.summarization = True
                    config.summary_type = aai.SummarizationType.paragraph
                elif summarization_type == "headline":
                    config.summarization = True
                    config.summary_type = aai.SummarizationType.headline

            logger.info(
                f"Starting AssemblyAI transcription: model={model}, "
                f"url={audio_url[:50]}..., features={self._list_enabled_features(**locals())}"
            )

            # Submit transcription (synchronous - SDK handles polling)
            transcript = client.transcribe(audio_url, config=config)

            # Check for errors
            if transcript.status == aai.TranscriptStatus.error:
                raise Exception(f"Transcription failed: {transcript.error}")

            # Extract audio duration (in seconds)
            audio_duration = transcript.audio_duration if hasattr(transcript, 'audio_duration') else 0

            # Calculate cost
            cost_usd = self._calculate_transcription_cost(
                model=model,
                audio_duration_seconds=audio_duration,
                speaker_labels=speaker_labels,
                sentiment_analysis=sentiment_analysis,
                entity_detection=entity_detection,
                auto_chapters=auto_chapters,
                summarization=summarization,
                iab_categories=iab_categories,
                content_safety=content_safety
            )

            # Build response content
            response_content = {
                "text": transcript.text,
                "audio_duration": audio_duration,
                "confidence": transcript.confidence if hasattr(transcript, 'confidence') else None,
                "language_code": transcript.language_code if hasattr(transcript, 'language_code') else None,
            }

            # Add optional features
            if speaker_labels and hasattr(transcript, 'utterances') and transcript.utterances:
                response_content["utterances"] = [
                    {
                        "speaker": utt.speaker,
                        "text": utt.text,
                        "start": utt.start,
                        "end": utt.end,
                        "confidence": utt.confidence
                    }
                    for utt in transcript.utterances
                ]

            if auto_chapters and hasattr(transcript, 'chapters') and transcript.chapters:
                response_content["chapters"] = [
                    {
                        "headline": ch.headline,
                        "summary": ch.summary,
                        "gist": ch.gist,
                        "start": ch.start,
                        "end": ch.end
                    }
                    for ch in transcript.chapters
                ]

            if entity_detection and hasattr(transcript, 'entities') and transcript.entities:
                response_content["entities"] = [
                    {
                        "entity_type": ent.entity_type,
                        "text": ent.text,
                        "start": ent.start,
                        "end": ent.end
                    }
                    for ent in transcript.entities
                ]

            if sentiment_analysis and hasattr(transcript, 'sentiment_analysis_results'):
                response_content["sentiment_analysis_results"] = [
                    {
                        "text": sent.text,
                        "sentiment": sent.sentiment,
                        "confidence": sent.confidence,
                        "start": sent.start,
                        "end": sent.end
                    }
                    for sent in transcript.sentiment_analysis_results
                ]

            if iab_categories and hasattr(transcript, 'iab_categories_result'):
                response_content["iab_categories_result"] = {
                    "summary": transcript.iab_categories_result.summary,
                    "results": [
                        {
                            "text": result.text,
                            "labels": [
                                {
                                    "label": label.label,
                                    "relevance": label.relevance
                                }
                                for label in result.labels
                            ]
                        }
                        for result in transcript.iab_categories_result.results
                    ]
                }

            if content_safety and hasattr(transcript, 'content_safety_labels'):
                response_content["content_safety_labels"] = {
                    "status": transcript.content_safety_labels.status,
                    "results": [
                        {
                            "text": result.text,
                            "labels": [
                                {
                                    "label": label.label,
                                    "confidence": label.confidence,
                                    "severity": label.severity
                                }
                                for label in result.labels
                            ]
                        }
                        for result in transcript.content_safety_labels.results
                    ]
                }

            if summarization and hasattr(transcript, 'summary'):
                response_content["summary"] = transcript.summary

            # Add words with timestamps if available
            if hasattr(transcript, 'words') and transcript.words:
                response_content["words"] = [
                    {
                        "text": word.text,
                        "start": word.start,
                        "end": word.end,
                        "confidence": word.confidence
                    }
                    for word in transcript.words[:100]  # Limit to first 100 words to save space
                ]

            # Pseudo-tokens: duration_seconds × 100 (for billing compatibility)
            pseudo_tokens = int(audio_duration * 100)

            logger.info(
                "assemblyai_transcribe_success",
                model=model,
                duration=audio_duration,
                confidence=response_content.get("confidence"),
                cost_usd=cost_usd
            )

            return LLMResponse(
                content=response_content,
                input_tokens=pseudo_tokens,  # Duration-based pseudo-tokens
                output_tokens=0,  # Transcription doesn't generate tokens
                cost_usd=cost_usd,
                provider_metadata={
                    "audio_duration": audio_duration,
                    "language_code": transcript.language_code if hasattr(transcript, 'language_code') else None,
                    "model": model,
                    "features_enabled": self._list_enabled_features(**locals())
                }
            )

        except Exception as e:
            logger.error(f"AssemblyAI transcription failed: {str(e)}", model=model)
            raise Exception(f"AssemblyAI transcription failed: {str(e)}")

    def _list_enabled_features(self, **kwargs) -> List[str]:
        """List which audio intelligence features are enabled"""
        features = []
        if kwargs.get("speaker_labels"):
            features.append("speaker_labels")
        if kwargs.get("sentiment_analysis"):
            features.append("sentiment_analysis")
        if kwargs.get("entity_detection"):
            features.append("entity_detection")
        if kwargs.get("auto_chapters"):
            features.append("auto_chapters")
        if kwargs.get("summarization"):
            features.append("summarization")
        if kwargs.get("iab_categories"):
            features.append("iab_categories")
        if kwargs.get("content_safety"):
            features.append("content_safety")
        return features

    def _calculate_transcription_cost(
        self,
        model: str,
        audio_duration_seconds: float,
        **features
    ) -> float:
        """
        Calculate cost for transcription with add-ons

        Args:
            model: "best" or "nano"
            audio_duration_seconds: Audio duration in seconds
            **features: Boolean flags for each feature

        Returns:
            Total cost in USD
        """
        # Convert to hours
        duration_hours = audio_duration_seconds / 3600

        # Base model cost
        model_rates = {
            "best": 0.37,
            "nano": 0.12,
        }
        base_cost = duration_hours * model_rates.get(model, 0.37)

        # Add-on costs
        addon_cost = 0.0
        for feature_name, rate_per_hour in self.ADD_ON_PRICING.items():
            if features.get(feature_name, False):
                addon_cost += duration_hours * rate_per_hour

        total_cost = base_cost + addon_cost
        return round(total_cost, 6)


# Auto-register this provider
def register():
    from src.providers import ProviderRegistry
    ProviderRegistry.register(AssemblyAIProvider)
