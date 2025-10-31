"""
Perspective Provider - Google's Toxicity & Content Moderation API
Fast, accurate ML-based content moderation with ~100ms response time
"""

from typing import Dict, Any, List, Optional
import time

from src.providers.base import BaseProvider, LLMResponse, ProviderConfig, ProviderMetadata
from src.utils.logger import logger


class PerspectiveProvider(BaseProvider):
    """
    Google Perspective API provider for content moderation

    Supported attributes:
    - TOXICITY (primary): Overall toxicity likelihood
    - SEVERE_TOXICITY: Very hateful, aggressive, disrespectful comments
    - IDENTITY_ATTACK: Negative or hateful comments about identity
    - INSULT: Insulting, inflammatory, or negative comments
    - PROFANITY: Swear words, curse words, or other obscene language
    - THREAT: Describes an intention to inflict pain, injury, or violence

    Experimental attributes:
    - OBSCENE: Obscene or vulgar language
    - SPAM: Irrelevant or unsolicited commercial content
    - ATTACK_ON_COMMENTER: Attack on fellow commenter
    - ATTACK_ON_AUTHOR: Attack on article author

    Key advantages:
    - **Fast**: ~100ms response time (100x faster than LLM moderation)
    - **Free**: No cost for default 1 QPS quota
    - **Accurate**: Specialized model trained on toxicity data
    - **Multilingual**: Supports 18 languages
    - **Per-sentence**: Can analyze individual sentences
    - **Privacy**: doNotStore flag for GDPR compliance

    Operations:
    - analyze: Analyze text for toxicity attributes
    - batch_analyze: Analyze multiple texts (future enhancement)
    """

    # Production-ready attributes
    PRODUCTION_ATTRIBUTES = [
        "TOXICITY",
        "SEVERE_TOXICITY",
        "IDENTITY_ATTACK",
        "INSULT",
        "PROFANITY",
        "THREAT"
    ]

    # Experimental attributes (may have lower accuracy)
    EXPERIMENTAL_ATTRIBUTES = [
        "OBSCENE",
        "SPAM",
        "ATTACK_ON_COMMENTER",
        "ATTACK_ON_AUTHOR",
        "INCOHERENT",
        "INFLAMMATORY",
        "LIKELY_TO_REJECT",
        "SEXUALLY_EXPLICIT"
    ]

    # Supported languages (18 languages)
    SUPPORTED_LANGUAGES = [
        "ar", "zh", "cs", "nl", "en", "fr", "de", "hi", "hi-Latn",
        "id", "it", "ja", "ko", "pl", "pt", "ru", "es", "sv"
    ]

    # API endpoint
    DISCOVER_SERVICE_URL = "https://commentanalyzer.googleapis.com/$discovery/rest?version=v1alpha1"

    @property
    def provider_name(self) -> str:
        return "perspective"

    def is_available(self) -> bool:
        """Check if Perspective API key is configured"""
        return self.config.api_key is not None and len(self.config.api_key) > 0

    def get_models(self) -> List[str]:
        """Return available analysis types as 'models'"""
        return ["toxicity", "moderation-full", "identity-attack", "profanity"]

    def get_metadata(self) -> ProviderMetadata:
        """Provider information for UI display"""
        return ProviderMetadata(
            display_name="Perspective API",
            description="Google's ML-powered content moderation API. Analyzes text for "
                        "toxicity, hate speech, profanity, and threats with ~100ms response time. "
                        "Free tier with 1 QPS quota. Supports 18 languages and per-sentence analysis.",
            logo_url="https://www.gstatic.com/images/branding/product/1x/google_cloud_48dp.png",
            website_url="https://perspectiveapi.com",
            requires_api_key=True,
            requires_base_url=False
        )

    def _get_client(self):
        """Lazy-load Google API Discovery client"""
        if self._client is None:
            try:
                from googleapiclient import discovery

                self._client = discovery.build(
                    "commentanalyzer",
                    "v1alpha1",
                    developerKey=self.config.api_key,
                    discoveryServiceUrl=self.DISCOVER_SERVICE_URL,
                    static_discovery=False
                )
                logger.info("Initialized Perspective API client")
            except ImportError:
                raise ImportError(
                    "google-api-python-client package not installed. "
                    "Install with: pip install google-api-python-client google-auth"
                )
            except Exception as e:
                logger.error(f"Failed to initialize Perspective client: {str(e)}")
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
        Route to analysis operation

        Operations:
        - analyze: Analyze text for toxicity (text kwarg required)
        - batch_analyze: Analyze multiple texts (future enhancement)
        """
        if not self.is_available():
            raise ValueError(
                "Perspective provider not configured. "
                "Set PERSPECTIVE_API_KEY in .env"
            )

        operation = kwargs.get("operation", "analyze")

        if operation == "analyze":
            return await self._analyze(**kwargs)
        elif operation == "batch_analyze":
            raise NotImplementedError(
                "Batch analysis not yet implemented. "
                "Use operation='analyze' for single text analysis."
            )
        else:
            raise ValueError(
                f"Unknown operation '{operation}'. "
                f"Supported: analyze, batch_analyze"
            )

    async def _analyze(
        self,
        text: str = None,

        # Requested attributes
        requested_attributes: Optional[List[str]] = None,

        # Language settings
        languages: Optional[List[str]] = None,

        # Privacy settings
        do_not_store: bool = True,

        # Advanced options
        span_annotations: bool = False,  # Per-sentence scoring
        community_id: Optional[str] = None,
        client_token: Optional[str] = None,
        session_id: Optional[str] = None,

        **kwargs
    ) -> LLMResponse:
        """
        Analyze text with Perspective API

        Args:
            text: Text to analyze (REQUIRED)
            requested_attributes: List of attributes to analyze (default: ["TOXICITY"])
            languages: Language hints (e.g., ["en", "es"])
            do_not_store: Don't store comment for future research (default: True for privacy)
            span_annotations: Return per-sentence scores
            community_id: Optional community identifier for customized models
            client_token: Optional client identifier for rate limiting
            session_id: Optional session identifier

        Returns:
            LLMResponse with attribute scores and analysis results
        """
        if not text:
            raise ValueError("'text' parameter required for analysis")

        # Default to TOXICITY if no attributes specified
        if not requested_attributes:
            requested_attributes = ["TOXICITY"]

        # Validate attributes
        all_attributes = self.PRODUCTION_ATTRIBUTES + self.EXPERIMENTAL_ATTRIBUTES
        for attr in requested_attributes:
            if attr not in all_attributes:
                logger.warning(
                    f"Unknown attribute '{attr}'. "
                    f"Supported: {', '.join(all_attributes)}"
                )

        try:
            client = self._get_client()

            # Build analyze request
            analyze_request = {
                "comment": {"text": text},
                "requestedAttributes": {
                    attr: {} for attr in requested_attributes
                },
                "doNotStore": do_not_store
            }

            # Add optional parameters
            if languages:
                # Validate language codes
                for lang in languages:
                    if lang not in self.SUPPORTED_LANGUAGES:
                        logger.warning(
                            f"Language '{lang}' may not be fully supported. "
                            f"Supported: {', '.join(self.SUPPORTED_LANGUAGES)}"
                        )
                analyze_request["languages"] = languages

            if span_annotations:
                analyze_request["spanAnnotations"] = True

            if community_id:
                analyze_request["communityId"] = community_id

            if client_token:
                analyze_request["clientToken"] = client_token

            if session_id:
                analyze_request["sessionId"] = session_id

            logger.info(
                f"Starting Perspective analysis: "
                f"text_len={len(text)}, attributes={requested_attributes}, "
                f"languages={languages}, do_not_store={do_not_store}"
            )

            # Call Perspective API
            response = client.comments().analyze(body=analyze_request).execute()

            # Extract attribute scores
            attribute_scores = {}
            for attr in requested_attributes:
                if attr in response.get("attributeScores", {}):
                    score_data = response["attributeScores"][attr]
                    attribute_scores[attr] = {
                        "summary_score": score_data["summaryScore"]["value"],
                        "summary_type": score_data["summaryScore"].get("type", "PROBABILITY"),
                        "span_scores": []
                    }

                    # Add per-sentence scores if requested
                    if span_annotations and "spanScores" in score_data:
                        attribute_scores[attr]["span_scores"] = [
                            {
                                "begin": span["begin"],
                                "end": span["end"],
                                "score": span["score"]["value"]
                            }
                            for span in score_data["spanScores"]
                        ]

            # Detect languages if provided
            detected_languages = response.get("languages", [])

            # Build response content
            response_content = {
                "attribute_scores": attribute_scores,
                "detected_languages": detected_languages,
                "text_length": len(text),
                "attributes_analyzed": requested_attributes
            }

            # Add overall toxicity flag and severity
            if "TOXICITY" in attribute_scores:
                toxicity_score = attribute_scores["TOXICITY"]["summary_score"]
                response_content["is_toxic"] = toxicity_score >= 0.5
                response_content["toxicity_level"] = self._get_severity_level(toxicity_score)
                response_content["toxicity_score"] = toxicity_score

            # Calculate cost (free, but track usage)
            cost_usd = 0.0  # Perspective API is free

            # Pseudo-tokens: text_length / 10 (for billing compatibility)
            pseudo_tokens = int(len(text) / 10) or 1

            logger.info(
                "perspective_analyze_success",
                text_length=len(text),
                attributes_analyzed=len(requested_attributes),
                toxicity_score=response_content.get("toxicity_score"),
                cost_usd=cost_usd
            )

            return LLMResponse(
                content=response_content,
                input_tokens=pseudo_tokens,
                output_tokens=0,  # Analysis doesn't generate tokens
                cost_usd=cost_usd,
                provider_metadata={
                    "text_length": len(text),
                    "attributes_analyzed": requested_attributes,
                    "detected_languages": detected_languages,
                    "span_annotations": span_annotations,
                    "do_not_store": do_not_store
                }
            )

        except Exception as e:
            logger.error(f"Perspective analysis failed: {str(e)}")
            raise Exception(f"Perspective analysis failed: {str(e)}")

    def _get_severity_level(self, score: float) -> str:
        """
        Convert probability score to severity level

        Args:
            score: Probability score (0-1)

        Returns:
            Severity level: "low", "medium", "high", "very_high"
        """
        if score < 0.3:
            return "low"
        elif score < 0.5:
            return "medium"
        elif score < 0.7:
            return "high"
        else:
            return "very_high"

    def _list_enabled_features(self, **kwargs) -> List[str]:
        """List which features are enabled"""
        features = []
        if kwargs.get("span_annotations"):
            features.append("span_annotations")
        if kwargs.get("languages"):
            features.append("language_detection")
        if kwargs.get("do_not_store"):
            features.append("privacy_mode")
        return features


# Auto-register this provider
def register():
    from src.providers import ProviderRegistry
    ProviderRegistry.register(PerspectiveProvider)
