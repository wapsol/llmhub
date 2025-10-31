"""
Groq Provider
Fast inference with OpenAI-compatible API
"""

from typing import List, Dict, Any, Optional
from openai import OpenAI
from src.providers.base import BaseProvider, LLMResponse, ProviderConfig, ProviderMetadata
from src.utils.logger import logger


class GroqProvider(BaseProvider):
    """Groq provider implementation"""

    @property
    def provider_name(self) -> str:
        return "groq"

    def is_available(self) -> bool:
        return bool(self.config.api_key)

    def _get_client(self) -> OpenAI:
        """Lazy client initialization"""
        if not self._client and self.config.api_key:
            # Groq uses OpenAI-compatible API
            self._client = OpenAI(
                api_key=self.config.api_key,
                base_url=self.config.base_url or "https://api.groq.com/openai/v1"
            )
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
        """Call Groq API (OpenAI-compatible)"""
        if not self.is_available():
            raise ValueError("Groq API key not configured")

        client = self._get_client()

        # Prepare messages
        groq_messages = []
        if system_prompt:
            groq_messages.append({"role": "system", "content": system_prompt})

        groq_messages.extend(messages)

        # Call API
        response = client.chat.completions.create(
            model=model,
            messages=groq_messages,
            max_tokens=max_tokens or 4096,
            temperature=temperature if temperature is not None else 0.7,
            **kwargs
        )

        # Extract response
        content = response.choices[0].message.content or ""
        input_tokens = response.usage.prompt_tokens
        output_tokens = response.usage.completion_tokens

        # Calculate cost
        cost_usd = self.calculate_cost(model, input_tokens, output_tokens)

        return LLMResponse(
            content=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            provider_metadata={
                "model": response.model,
                "finish_reason": response.choices[0].finish_reason
            }
        )

    def get_models(self) -> List[str]:
        return [
            "mixtral-8x7b-32768",
            "llama2-70b-4096",
            "gemma-7b-it"
        ]

    def get_metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            display_name="Groq",
            description="Ultra-fast inference with open-source models on custom LPU hardware",
            logo_url="https://groq.com/wp-content/uploads/2024/03/PrimaryLogo-min.svg",
            website_url="https://groq.com",
            requires_api_key=True,
            requires_base_url=False
        )


# Auto-register this provider
def register():
    from src.providers import ProviderRegistry
    ProviderRegistry.register(GroqProvider)
