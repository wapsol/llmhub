"""
LLM Core Service - Refactored with Provider Registry
Multi-provider LLM integration with cost tracking and error handling
"""

from typing import Dict, Any, List, Optional
import time
import yaml
from pathlib import Path

from src.providers import ProviderRegistry
from src.providers.base import ProviderConfig
from src.config.settings import settings
from src.utils.logger import logger


class LLMCoreService:
    """
    Core service for LLM API calls with multi-provider support

    Now uses the provider registry pattern for scalable provider management
    """

    def __init__(self):
        """Initialize all available providers from config"""
        self._initialize_providers()

    def _initialize_providers(self):
        """Load provider configurations and initialize"""
        # Load pricing config
        pricing_config = self._load_pricing_config()

        # Configure all providers
        providers_config = {
            "claude": ProviderConfig(
                name="claude",
                api_key=settings.ANTHROPIC_API_KEY,
                default_model="claude-3-5-sonnet-20241022",
                pricing=pricing_config.get("anthropic", {})
            ),
            "openai": ProviderConfig(
                name="openai",
                api_key=settings.OPENAI_API_KEY,
                default_model="gpt-4-turbo",
                pricing=pricing_config.get("openai", {})
            ),
            "groq": ProviderConfig(
                name="groq",
                api_key=settings.GROQ_API_KEY,
                base_url="https://api.groq.com/openai/v1",
                default_model="mixtral-8x7b-32768",
                pricing=pricing_config.get("groq", {})
            ),
            "google": ProviderConfig(
                name="google",
                api_key=settings.GOOGLE_API_KEY,
                default_model="gemini-1.5-pro",
                pricing=pricing_config.get("google", {})
            ),
            "mistral": ProviderConfig(
                name="mistral",
                api_key=settings.MISTRAL_API_KEY,
                default_model="mistral-large-latest",
                pricing=pricing_config.get("mistral", {})
            ),
            "cohere": ProviderConfig(
                name="cohere",
                api_key=settings.COHERE_API_KEY,
                default_model="command-r-plus",
                pricing=pricing_config.get("cohere", {})
            ),
            "ollama": ProviderConfig(
                name="ollama",
                api_key=None,  # No key needed for local Ollama
                base_url=getattr(settings, 'OLLAMA_BASE_URL', None) or "http://localhost:11434",
                default_model="llama2",
                pricing=pricing_config.get("ollama", {})
            ),
            "runway": ProviderConfig(
                name="runway",
                api_key=settings.RUNWAY_API_KEY,
                default_model="gen4_turbo",
                pricing=pricing_config.get("runway", {})
            ),
            "pika": ProviderConfig(
                name="pika",
                api_key=settings.FAL_KEY,
                default_model="pika-2.2-720p",
                pricing=pricing_config.get("pika", {})
            ),
            "elevenlabs": ProviderConfig(
                name="elevenlabs",
                api_key=settings.ELEVENLABS_API_KEY,
                default_model="eleven_flash_v2_5",
                pricing=pricing_config.get("elevenlabs", {})
            ),
            "voyageai": ProviderConfig(
                name="voyageai",
                api_key=settings.VOYAGE_API_KEY,
                default_model="voyage-3.5-lite",
                pricing=pricing_config.get("voyageai", {})
            ),
            "assemblyai": ProviderConfig(
                name="assemblyai",
                api_key=settings.ASSEMBLYAI_API_KEY,
                default_model="best",
                pricing=pricing_config.get("assemblyai", {})
            ),
            "deepgram": ProviderConfig(
                name="deepgram",
                api_key=settings.DEEPGRAM_API_KEY,
                default_model="nova-3",
                pricing=pricing_config.get("deepgram", {})
            ),
            "perspective": ProviderConfig(
                name="perspective",
                api_key=settings.PERSPECTIVE_API_KEY,
                default_model="toxicity",
                pricing=pricing_config.get("perspective", {})
            )
        }

        # Initialize each provider
        for provider_name, config in providers_config.items():
            ProviderRegistry.initialize_provider(provider_name, config)

        # Log available providers
        available = ProviderRegistry.get_available_providers()
        logger.info(f"Initialized providers: {', '.join(available)}")

    def _load_pricing_config(self) -> Dict[str, Any]:
        """Load pricing from YAML config file"""
        pricing_file = Path(__file__).parent.parent / "config" / "provider_pricing.yaml"

        if not pricing_file.exists():
            logger.warning("Pricing config not found, using defaults")
            return {}

        try:
            with open(pricing_file) as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"Failed to load pricing config: {e}")
            return {}

    async def call_llm(
        self,
        provider: str,
        model: str,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Call LLM provider with unified interface

        Args:
            provider: 'claude', 'openai', 'groq', 'google', 'mistral', or 'ollama'
            model: Model identifier
            messages: List of message dicts [{"role": "user", "content": "..."}]
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature (0-2)
            system_prompt: Optional system prompt

        Returns:
            Dict with keys: content, input_tokens, output_tokens, cost_usd, generation_time_ms

        Raises:
            ValueError: If provider not configured or invalid
            Exception: On API errors (with retry logic)
        """
        start_time = time.time()

        # Validate inputs
        if not messages or len(messages) == 0:
            raise ValueError("Messages cannot be empty")

        # Get provider from registry
        provider_instance = ProviderRegistry.get_provider(provider.lower())
        if not provider_instance:
            available = ProviderRegistry.get_available_providers()
            raise ValueError(
                f"Provider '{provider}' not available. "
                f"Available providers: {', '.join(available)}"
            )

        # Call provider
        try:
            response = await provider_instance.call(
                model=model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                system_prompt=system_prompt,
                **kwargs
            )

            # Calculate generation time
            generation_time_ms = int((time.time() - start_time) * 1000)

            # Convert to dict for backward compatibility
            result = {
                "content": response.content,
                "input_tokens": response.input_tokens,
                "output_tokens": response.output_tokens,
                "cost_usd": response.cost_usd,
                "generation_time_ms": generation_time_ms
            }

            logger.info(
                "llm_call_success",
                provider=provider,
                model=model,
                input_tokens=result.get("input_tokens"),
                output_tokens=result.get("output_tokens"),
                cost_usd=result.get("cost_usd"),
                generation_time_ms=generation_time_ms
            )

            return result

        except Exception as e:
            generation_time_ms = int((time.time() - start_time) * 1000)
            logger.error(
                "llm_call_failed",
                provider=provider,
                model=model,
                error=str(e),
                generation_time_ms=generation_time_ms
            )
            raise

    def get_available_providers(self) -> List[str]:
        """Get list of available providers"""
        return ProviderRegistry.get_available_providers()

    def get_provider_models(self, provider: str) -> List[str]:
        """Get supported models for a provider"""
        provider_instance = ProviderRegistry.get_provider(provider.lower())
        if not provider_instance:
            return []
        return provider_instance.get_models()

    def count_tokens(self, text: str, model: str = "gpt-4") -> int:
        """
        Count tokens in text using tiktoken

        Args:
            text: Text to count tokens for
            model: Model name for encoding (default: gpt-4)

        Returns:
            Number of tokens
        """
        try:
            import tiktoken
            encoding = tiktoken.encoding_for_model(model)
            return len(encoding.encode(text))
        except Exception as e:
            logger.warning(f"Token counting error: {str(e)}, using fallback")
            # Fallback: rough estimate (1 token ~= 4 characters)
            return len(text) // 4


# Create global instance
llm_core = LLMCoreService()
