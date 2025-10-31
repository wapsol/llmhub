"""
OpenAI Provider
"""

from typing import List, Dict, Any, Optional
from openai import OpenAI
from src.providers.base import BaseProvider, LLMResponse, ProviderConfig, ProviderMetadata
from src.utils.logger import logger


class OpenAIProvider(BaseProvider):
    """OpenAI provider implementation"""

    @property
    def provider_name(self) -> str:
        return "openai"

    def is_available(self) -> bool:
        return bool(self.config.api_key)

    def _get_client(self) -> OpenAI:
        """Lazy client initialization"""
        if not self._client and self.config.api_key:
            self._client = OpenAI(api_key=self.config.api_key)
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
        """Call OpenAI API"""
        if not self.is_available():
            raise ValueError("OpenAI API key not configured")

        client = self._get_client()

        # Prepare messages
        openai_messages = []
        if system_prompt:
            openai_messages.append({"role": "system", "content": system_prompt})

        openai_messages.extend(messages)

        # Call API
        response = client.chat.completions.create(
            model=model,
            messages=openai_messages,
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
            "gpt-4-turbo",
            "gpt-4",
            "gpt-3.5-turbo"
        ]

    def get_metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            display_name="OpenAI",
            description="GPT-4 and DALL-E image generation with wide ecosystem support",
            logo_url="https://openai.com/favicon.ico",
            website_url="https://openai.com",
            requires_api_key=True,
            requires_base_url=False
        )


# Auto-register this provider
def register():
    from src.providers import ProviderRegistry
    ProviderRegistry.register(OpenAIProvider)
