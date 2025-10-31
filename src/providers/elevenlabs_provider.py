"""
ElevenLabs Text-to-Speech Provider
Premium voice synthesis with advanced voice controls
"""

from typing import List, Dict, Any, Optional
from elevenlabs import ElevenLabs
from src.providers.base import BaseProvider, LLMResponse, ProviderConfig, ProviderMetadata
from src.utils.logger import logger


class ElevenLabsProvider(BaseProvider):
    """
    ElevenLabs provider for text-to-speech synthesis

    Supported models:
    - eleven_flash_v2_5 (default): Fastest, 75ms latency, 0.5 credits/char
    - eleven_turbo_v2_5: High quality, low latency, 1 credit/char
    - eleven_multilingual_v2: Best quality, 29 languages, 1 credit/char
    - eleven_turbo_v2: Previous gen turbo, 1 credit/char
    - eleven_multilingual_v1: Legacy multilingual, 1 credit/char
    - eleven_monolingual_v1: Legacy English-only, 1 credit/char
    """

    # Cost per character in USD (based on Growing Business tier: $165/1M chars)
    MODEL_COSTS_PER_CHAR = {
        # Flash models (0.5 credits per character)
        "eleven_flash_v2_5": 0.00008,   # 50% cheaper
        "eleven_flash_v2": 0.00008,

        # Standard models (1 credit per character)
        "eleven_multilingual_v2": 0.00016,
        "eleven_turbo_v2_5": 0.00016,
        "eleven_turbo_v2": 0.00016,
        "eleven_multilingual_v1": 0.00016,
        "eleven_monolingual_v1": 0.00016,
    }

    # Default premade voices (professional use cases)
    DEFAULT_VOICES = {
        "professional_male": "ErXwobaYiN019PkySvjV",      # Antoni - deep, calm
        "professional_female": "EXAVITQu4vr4xnSDxMaL",    # Bella - friendly, clear
        "friendly_male": "VR6AewLTigWG4xSOukaG",          # Arnold - warm
        "friendly_female": "jsCqWAovK2LkecY7zXl4",        # Freya - upbeat
        "default": "JBFqnCBsd6RMkjVDRZzb"                 # George - neutral
    }

    @property
    def provider_name(self) -> str:
        return "elevenlabs"

    def is_available(self) -> bool:
        """Check if ElevenLabs API key is configured"""
        return bool(self.config.api_key)

    def _get_client(self) -> ElevenLabs:
        """Lazy client initialization"""
        if not self._client and self.config.api_key:
            self._client = ElevenLabs(api_key=self.config.api_key)
        return self._client

    def _resolve_voice_id(self, voice_identifier: str) -> str:
        """
        Resolve voice identifier to voice ID

        Accepts:
        - Voice ID directly: "ErXwobaYiN019PkySvjV"
        - Named voice: "professional_male" -> resolves to ID
        """
        # If it's a named voice, resolve it
        if voice_identifier in self.DEFAULT_VOICES:
            return self.DEFAULT_VOICES[voice_identifier]

        # Otherwise assume it's already a voice ID
        return voice_identifier

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
        Generate speech using ElevenLabs TTS

        Note: ElevenLabs is audio-focused, so it doesn't use traditional messages.
        Instead, kwargs should contain TTS parameters:
        - text: Text to convert to speech (REQUIRED)
        - voice: Voice identifier or ID (default: "default")
        - output_format: Audio format (default: "mp3_44100_128")
        - stability: Voice stability 0-1 (default: 0.5)
        - similarity_boost: Voice similarity 0-1 (default: 0.75)
        - style: Speaking style 0-1 (default: 0.0)
        - use_speaker_boost: Enhance clarity (default: True)
        """
        if not self.is_available():
            raise ValueError("ElevenLabs API key not configured (ELEVENLABS_API_KEY required)")

        client = self._get_client()

        # Extract TTS-specific parameters
        text = kwargs.get("text", "")
        if not text:
            raise ValueError("Parameter 'text' is required for text-to-speech")

        voice_identifier = kwargs.get("voice", "default")
        voice_id = self._resolve_voice_id(voice_identifier)

        output_format = kwargs.get("output_format", "mp3_44100_128")

        # Voice settings (ElevenLabs' secret sauce)
        voice_settings = {
            "stability": kwargs.get("stability", 0.5),
            "similarity_boost": kwargs.get("similarity_boost", 0.75),
            "style": kwargs.get("style", 0.0),
            "use_speaker_boost": kwargs.get("use_speaker_boost", True)
        }

        try:
            logger.info(
                f"Starting ElevenLabs TTS: model={model}, voice_id={voice_id[:8]}..., "
                f"format={output_format}, text_length={len(text)} chars"
            )

            # Call ElevenLabs API
            audio_generator = client.text_to_speech.convert(
                voice_id=voice_id,
                text=text,
                model_id=model,
                output_format=output_format,
                voice_settings=voice_settings
            )

            # Collect audio bytes
            audio_bytes = b""
            for chunk in audio_generator:
                audio_bytes += chunk

            # Calculate cost based on character count
            char_count = len(text)
            cost_usd = self._calculate_audio_cost(model, char_count)

            # For billing tracking: use character-based pseudo-tokens
            # 1 character = 100 tokens (for compatibility with token-based system)
            pseudo_tokens = char_count * 100

            logger.info(
                f"ElevenLabs TTS completed: chars={char_count}, "
                f"audio_size={len(audio_bytes)} bytes, cost=${cost_usd}"
            )

            # Return audio data as base64 or we could upload to MinIO
            # For now, return as content (caller will handle storage)
            import base64
            audio_base64 = base64.b64encode(audio_bytes).decode('utf-8')

            return LLMResponse(
                content=audio_base64,  # Base64-encoded audio
                input_tokens=pseudo_tokens,  # Character count * 100
                output_tokens=0,
                cost_usd=cost_usd,
                provider_metadata={
                    "model": model,
                    "voice_id": voice_id,
                    "output_format": output_format,
                    "character_count": char_count,
                    "audio_size_bytes": len(audio_bytes),
                    "voice_settings": voice_settings
                }
            )

        except Exception as e:
            logger.error(f"ElevenLabs TTS generation failed: {str(e)}")
            raise Exception(f"ElevenLabs TTS error: {str(e)}")

    def _calculate_audio_cost(self, model: str, char_count: int) -> float:
        """
        Calculate cost based on character count and model

        Args:
            model: Model identifier
            char_count: Number of characters in text

        Returns:
            Cost in USD
        """
        cost_per_char = self.MODEL_COSTS_PER_CHAR.get(model, 0.00016)
        return round(cost_per_char * char_count, 6)

    def get_models(self) -> List[str]:
        return [
            "eleven_flash_v2_5",        # Fastest, cheapest
            "eleven_turbo_v2_5",        # High quality, low latency
            "eleven_multilingual_v2",   # Best quality
            "eleven_flash_v2",          # Previous gen flash
            "eleven_turbo_v2",          # Previous gen turbo
            "eleven_multilingual_v1",   # Legacy multilingual
            "eleven_monolingual_v1"     # Legacy English
        ]

    def get_metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            display_name="ElevenLabs",
            description="Premium AI text-to-speech with the most realistic and expressive voices. "
                        "Supports 32 languages, voice cloning, and 75ms latency for real-time applications.",
            logo_url="https://elevenlabs.io/favicon.ico",
            website_url="https://elevenlabs.io",
            requires_api_key=True,
            requires_base_url=False
        )

    def calculate_cost(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int
    ) -> float:
        """
        Override base calculate_cost since ElevenLabs uses character-based pricing

        For ElevenLabs, input_tokens represents (character_count * 100)
        This allows us to use the standard token-based cost tracking system
        """
        char_count = input_tokens // 100
        return self._calculate_audio_cost(model, char_count)


# Auto-register this provider
def register():
    from src.providers import ProviderRegistry
    ProviderRegistry.register(ElevenLabsProvider)
