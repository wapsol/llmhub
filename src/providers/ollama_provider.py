"""
Ollama Provider
Local LLM inference with OpenAI-compatible API
"""

from typing import List, Dict, Optional
import httpx
from src.providers.base import BaseProvider, LLMResponse, ProviderConfig, ProviderMetadata
from src.utils.logger import logger


class OllamaProvider(BaseProvider):
    """Ollama local provider"""

    @property
    def provider_name(self) -> str:
        return "ollama"

    def is_available(self) -> bool:
        # Ollama typically runs locally, no API key needed
        # Just check if base_url is configured
        return bool(self.config.base_url)

    async def call(
        self,
        model: str,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        system_prompt: Optional[str] = None,
        **kwargs
    ) -> LLMResponse:
        """Call Ollama API"""
        if not self.is_available():
            raise ValueError("Ollama base URL not configured")

        # Prepare messages
        ollama_messages = []
        if system_prompt:
            ollama_messages.append({"role": "system", "content": system_prompt})
        ollama_messages.extend(messages)

        # Call Ollama API (OpenAI-compatible)
        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            response = await client.post(
                f"{self.config.base_url}/v1/chat/completions",
                json={
                    "model": model,
                    "messages": ollama_messages,
                    "max_tokens": max_tokens or 4096,
                    "temperature": temperature if temperature is not None else 0.7,
                    **kwargs
                }
            )
            response.raise_for_status()
            data = response.json()

        # Parse response (OpenAI format)
        content = data["choices"][0]["message"]["content"]
        input_tokens = data["usage"]["prompt_tokens"]
        output_tokens = data["usage"]["completion_tokens"]

        # Ollama is free (local), but we track "virtual" cost for consistency
        cost_usd = self.calculate_cost(model, input_tokens, output_tokens)

        return LLMResponse(
            content=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,  # Will be 0.0 from config
            provider_metadata={"model": data.get("model", model)}
        )

    def get_models(self) -> List[str]:
        # Could query Ollama API for available models in the future
        return [
            "llama2",
            "llama2:13b",
            "llama2:70b",
            "mistral",
            "mixtral",
            "codellama",
            "neural-chat",
            "starling-lm"
        ]

    def get_metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            display_name="Ollama",
            description="Run LLMs locally on your own hardware - Free and private",
            logo_url="https://ollama.ai/public/ollama.png",
            website_url="https://ollama.ai",
            requires_api_key=False,  # No API key needed for local inference
            requires_base_url=True   # Needs base URL configuration
        )


# Auto-register this provider
def register():
    from src.providers import ProviderRegistry
    ProviderRegistry.register(OllamaProvider)
