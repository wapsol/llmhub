"""
Deepgram Provider - Ultra-Fast Speech-to-Text
World's fastest speech recognition with sub-200ms latency and real-time streaming
"""

from typing import Dict, Any, List, Optional
import time

from src.providers.base import BaseProvider, LLMResponse, ProviderConfig, ProviderMetadata
from src.utils.logger import logger


class DeepgramProvider(BaseProvider):
    """
    Deepgram speech-to-text provider

    Supported models:
    - nova-3 (default): Flagship model, best accuracy, $0.258/hour
    - nova-3-multilingual: Code-switching across 10 languages
    - nova-3-medical: Healthcare-specialized transcription
    - nova-2: Previous generation, highly accurate
    - whisper-large: OpenAI Whisper via Deepgram (3x faster, 20% cheaper)

    Key advantages:
    - **Fastest**: Sub-200ms latency, 40x faster diarization
    - **Accurate**: 54% lower streaming WER vs competitors
    - **Multilingual**: First ASR with live code-switching
    - **Cost-effective**: $0.258/hour (30% cheaper than AssemblyAI)
    - **Per-second billing**: More granular than competitors
    - **Real-time ready**: Native WebSocket streaming support

    Operations:
    - transcribe: Convert audio to text with intelligence features
    - stream: Real-time streaming transcription (future enhancement)
    """

    # Supported models
    MODELS = [
        "nova-3",                # Flagship: Best accuracy, multilingual
        "nova-3-multilingual",   # 10-language code-switching
        "nova-3-medical",        # Healthcare specialization
        "nova-2",                # Previous generation
        "whisper-large",         # OpenAI Whisper (faster via Deepgram)
    ]

    @property
    def provider_name(self) -> str:
        return "deepgram"

    def is_available(self) -> bool:
        """Check if Deepgram API key is configured"""
        return self.config.api_key is not None and len(self.config.api_key) > 0

    def get_models(self) -> List[str]:
        """Return supported models"""
        return self.MODELS

    def get_metadata(self) -> ProviderMetadata:
        """Provider information for UI display"""
        return ProviderMetadata(
            display_name="Deepgram",
            description="World's fastest speech-to-text with sub-200ms latency. "
                        "Nova-3 delivers 54% lower streaming WER, real-time code-switching "
                        "across 10 languages, and 40x faster diarization. Includes smart "
                        "formatting, summarization, topics, sentiment, and keyword boosting.",
            logo_url="https://deepgram.com/favicon.ico",
            website_url="https://deepgram.com",
            requires_api_key=True,
            requires_base_url=False
        )

    def _get_client(self):
        """Lazy-load Deepgram client"""
        if self._client is None:
            try:
                from deepgram import DeepgramClient

                self._client = DeepgramClient(self.config.api_key)
                logger.info(f"Initialized Deepgram client")
            except ImportError:
                raise ImportError(
                    "deepgram-sdk package not installed. "
                    "Install with: pip install deepgram-sdk"
                )
            except Exception as e:
                logger.error(f"Failed to initialize Deepgram client: {str(e)}")
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
        - stream: Real-time streaming (future enhancement)
        """
        if not self.is_available():
            raise ValueError(
                "Deepgram provider not configured. "
                "Set DEEPGRAM_API_KEY in .env"
            )

        operation = kwargs.get("operation", "transcribe")

        if operation == "transcribe":
            return await self._transcribe(**kwargs)
        elif operation == "stream":
            raise NotImplementedError(
                "Real-time streaming not yet implemented. "
                "Use operation='transcribe' for pre-recorded audio."
            )
        else:
            raise ValueError(
                f"Unknown operation '{operation}'. "
                f"Supported: transcribe, stream"
            )

    async def _transcribe(
        self,
        audio_url: str = None,
        model: str = "nova-3",

        # Language and detection
        language_code: Optional[str] = None,
        detect_language: bool = False,

        # Formatting
        smart_format: bool = True,
        punctuate: bool = True,
        paragraphs: bool = False,
        numerals: bool = False,
        filler_words: bool = False,

        # Speaker diarization
        diarize: bool = False,
        utterances: bool = False,

        # Audio intelligence
        summarize: bool = False,
        topics: bool = False,
        custom_topics: Optional[List[str]] = None,
        sentiment: bool = False,
        intents: bool = False,

        # Keyword boosting
        keywords: Optional[List[str]] = None,
        keyword_boost: float = 2.0,

        # Content filtering
        profanity_filter: bool = False,
        redact: Optional[List[str]] = None,

        # Search
        search: Optional[List[str]] = None,
        replace: Optional[Dict[str, str]] = None,

        # Multi-channel
        multichannel: bool = False,

        **kwargs
    ) -> LLMResponse:
        """
        Transcribe audio with Deepgram's Nova-3 or other models

        Args:
            audio_url: Public URL to audio file (REQUIRED)
            model: "nova-3", "nova-3-multilingual", "nova-3-medical", "nova-2", "whisper-large"
            language_code: Language hint (e.g., "en", "es", "fr")
            detect_language: Auto-detect language
            smart_format: Smart formatting (punctuation, capitalization, paragraphing)
            punctuate: Add punctuation
            paragraphs: Segment into paragraphs
            numerals: Convert written numbers to digits
            filler_words: Include filler words (uh, um)
            diarize: Speaker diarization
            utterances: Return utterance-level results
            summarize: Generate summary
            topics: Detect topics
            custom_topics: Custom topics to detect
            sentiment: Sentiment analysis per utterance
            intents: Intent recognition
            keywords: Keywords to boost (up to 100)
            keyword_boost: Boost value (1.0-5.0, default 2.0)
            profanity_filter: Filter profanity
            redact: PII to redact (e.g., ["pii", "ssn", "credit_card"])
            search: Terms to search for
            replace: Find and replace terms
            multichannel: Multi-channel audio processing

        Returns:
            LLMResponse with transcript and intelligence results
        """
        if not audio_url:
            raise ValueError("'audio_url' parameter required for transcription")

        if model not in self.MODELS:
            raise ValueError(
                f"Invalid model '{model}'. "
                f"Supported: {', '.join(self.MODELS)}"
            )

        try:
            from deepgram import PrerecordedOptions

            client = self._get_client()

            # Build transcription options
            options = PrerecordedOptions(
                model=model,
                smart_format=smart_format,
                punctuate=punctuate if not smart_format else None,  # smart_format includes punctuation
                paragraphs=paragraphs,
                numerals=numerals,
                filler_words=filler_words,
                diarize=diarize,
                diarize_version="2024-09-24" if diarize else None,  # Latest version
                utterances=utterances if diarize else None,  # Requires diarization
                multichannel=multichannel,
                profanity_filter=profanity_filter,
            )

            # Language settings
            if detect_language:
                options.detect_language = True
            elif language_code:
                options.language = language_code

            # Audio intelligence features
            if summarize:
                options.summarize = "v2"  # Latest version

            if topics:
                options.topics = True
                if custom_topics:
                    options.custom_topics = custom_topics

            if sentiment:
                options.sentiment = True

            if intents:
                options.intents = True

            # Keyword boosting
            if keywords:
                # Format: ["keyword1:boost", "keyword2:boost"]
                keyword_list = [f"{kw}:{keyword_boost}" for kw in keywords[:100]]  # Limit 100
                options.keywords = keyword_list

            # PII redaction
            if redact:
                options.redact = redact

            # Search
            if search:
                options.search = search

            # Replace
            if replace:
                options.replace = replace

            logger.info(
                f"Starting Deepgram transcription: model={model}, "
                f"url={audio_url[:50]}..., features={self._list_enabled_features(**locals())}"
            )

            # Call Deepgram API
            response = client.listen.rest.v("1").transcribe_url(
                source={"url": audio_url},
                options=options
            )

            # Extract results
            channel = response.results.channels[0]
            alternative = channel.alternatives[0]

            # Basic transcript data
            transcript_text = alternative.transcript
            confidence = alternative.confidence if hasattr(alternative, 'confidence') else None

            # Audio duration (in seconds)
            audio_duration = response.metadata.duration if hasattr(response.metadata, 'duration') else 0

            # Build response content
            response_content = {
                "text": transcript_text,
                "audio_duration": audio_duration,
                "confidence": confidence,
                "model_info": response.metadata.model_info.__dict__ if hasattr(response.metadata, 'model_info') else {}
            }

            # Language detection
            if detect_language and hasattr(channel, 'detected_language'):
                response_content["detected_language"] = channel.detected_language
            elif language_code:
                response_content["language_code"] = language_code

            # Words with timestamps
            if hasattr(alternative, 'words') and alternative.words:
                response_content["words"] = [
                    {
                        "word": word.word,
                        "start": word.start,
                        "end": word.end,
                        "confidence": word.confidence if hasattr(word, 'confidence') else None
                    }
                    for word in alternative.words[:100]  # Limit to first 100 words
                ]

            # Paragraphs
            if paragraphs and hasattr(alternative, 'paragraphs') and alternative.paragraphs:
                response_content["paragraphs"] = [
                    {
                        "transcript": para.sentences[0].text if para.sentences else "",
                        "start": para.start if hasattr(para, 'start') else None,
                        "end": para.end if hasattr(para, 'end') else None
                    }
                    for para in alternative.paragraphs.paragraphs
                ]

            # Utterances (speaker diarization)
            if utterances and hasattr(channel, 'utterances') and channel.utterances:
                response_content["utterances"] = [
                    {
                        "speaker": utt.speaker,
                        "text": utt.transcript,
                        "start": utt.start,
                        "end": utt.end,
                        "confidence": utt.confidence if hasattr(utt, 'confidence') else None
                    }
                    for utt in channel.utterances
                ]

            # Summary
            if summarize and hasattr(response.results, 'summary'):
                response_content["summary"] = response.results.summary.short if hasattr(response.results.summary, 'short') else str(response.results.summary)

            # Topics
            if topics and hasattr(response.results, 'topics'):
                response_content["topics_detected"] = [
                    {
                        "topic": topic.topic if hasattr(topic, 'topic') else str(topic),
                        "confidence": topic.confidence if hasattr(topic, 'confidence') else None
                    }
                    for segment in response.results.topics.segments
                    for topic in segment.topics
                ] if hasattr(response.results.topics, 'segments') else []

            # Sentiment
            if sentiment and hasattr(response.results, 'sentiments'):
                response_content["sentiment_analysis_results"] = [
                    {
                        "text": seg.text if hasattr(seg, 'text') else "",
                        "sentiment": seg.sentiment if hasattr(seg, 'sentiment') else None,
                        "confidence": seg.sentiment_score if hasattr(seg, 'sentiment_score') else None,
                        "start": seg.start if hasattr(seg, 'start') else None,
                        "end": seg.end if hasattr(seg, 'end') else None
                    }
                    for seg in response.results.sentiments.segments
                ] if hasattr(response.results.sentiments, 'segments') else []

            # Intents
            if intents and hasattr(response.results, 'intents'):
                response_content["intents_detected"] = [
                    {
                        "intent": seg.intent if hasattr(seg, 'intent') else None,
                        "confidence": seg.intent_score if hasattr(seg, 'intent_score') else None
                    }
                    for seg in response.results.intents.segments
                ] if hasattr(response.results.intents, 'segments') else []

            # Search results
            if search and hasattr(response.results, 'search'):
                response_content["search_results"] = response.results.search

            # Calculate cost (per-second precision!)
            cost_usd = self._calculate_cost(audio_duration, model)

            # Pseudo-tokens: duration_seconds × 100 (for billing compatibility)
            pseudo_tokens = int(audio_duration * 100)

            logger.info(
                "deepgram_transcribe_success",
                model=model,
                duration=audio_duration,
                confidence=confidence,
                cost_usd=cost_usd
            )

            return LLMResponse(
                content=response_content,
                input_tokens=pseudo_tokens,  # Duration-based pseudo-tokens
                output_tokens=0,  # Transcription doesn't generate tokens
                cost_usd=cost_usd,
                provider_metadata={
                    "audio_duration": audio_duration,
                    "model": model,
                    "detected_language": response_content.get("detected_language"),
                    "features_enabled": self._list_enabled_features(**locals())
                }
            )

        except Exception as e:
            logger.error(f"Deepgram transcription failed: {str(e)}", model=model)
            raise Exception(f"Deepgram transcription failed: {str(e)}")

    def _list_enabled_features(self, **kwargs) -> List[str]:
        """List which features are enabled"""
        features = []
        feature_flags = [
            "smart_format", "diarize", "summarize", "topics",
            "sentiment", "intents", "detect_language", "keywords",
            "paragraphs", "utterances", "profanity_filter", "redact"
        ]
        for flag in feature_flags:
            if kwargs.get(flag):
                features.append(flag)
        return features

    def _calculate_cost(self, audio_duration_seconds: float, model: str) -> float:
        """
        Calculate cost for transcription (per-second precision!)

        Args:
            audio_duration_seconds: Audio duration in seconds
            model: Model name

        Returns:
            Total cost in USD
        """
        # Cost per minute
        cost_per_minute_map = {
            "nova-3": 0.0043,
            "nova-3-multilingual": 0.0043,
            "nova-3-medical": 0.0043,
            "nova-2": 0.0043,
            "whisper-large": 0.0048,
            # Streaming models (for future)
            "nova-3-streaming": 0.0059,
        }

        cost_per_minute = cost_per_minute_map.get(model, 0.0043)
        cost_per_second = cost_per_minute / 60

        # Per-second billing (Deepgram's advantage!)
        total_cost = audio_duration_seconds * cost_per_second
        return round(total_cost, 6)


# Auto-register this provider
def register():
    from src.providers import ProviderRegistry
    ProviderRegistry.register(DeepgramProvider)
