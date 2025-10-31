"""
Mistral AI Provider
"""

from typing import List, Dict, Any, Optional
from mistralai.client import MistralClient
from mistralai.models.chat_completion import ChatMessage
from src.providers.base import BaseProvider, LLMResponse, ProviderConfig, ProviderMetadata
from src.utils.logger import logger


class MistralProvider(BaseProvider):
    """Mistral AI provider implementation"""

    @property
    def provider_name(self) -> str:
        return "mistral"

    def is_available(self) -> bool:
        return bool(self.config.api_key)

    def _get_client(self) -> MistralClient:
        """Lazy client initialization"""
        if not self._client and self.config.api_key:
            self._client = MistralClient(api_key=self.config.api_key)
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
        """Call Mistral AI API"""
        if not self.is_available():
            raise ValueError("Mistral API key not configured")

        client = self._get_client()

        try:
            # Convert messages to Mistral format
            mistral_messages = []

            # Add system prompt if provided
            if system_prompt:
                mistral_messages.append(
                    ChatMessage(role="system", content=system_prompt)
                )

            # Add conversation messages
            for msg in messages:
                role = msg["role"]
                content = msg["content"]

                # Mistral supports: system, user, assistant
                if role in ["system", "user", "assistant"]:
                    mistral_messages.append(
                        ChatMessage(role=role, content=content)
                    )

            # Call API
            response = client.chat(
                model=model,
                messages=mistral_messages,
                max_tokens=max_tokens or 4096,
                temperature=temperature if temperature is not None else 0.7,
                **kwargs
            )

            # Extract response content
            content = response.choices[0].message.content

            # Get token counts from response
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

        except Exception as e:
            logger.error(f"Mistral API error: {str(e)}")
            raise

    def get_models(self) -> List[str]:
        return [
            "mistral-large-latest",
            "mistral-medium-latest",
            "mistral-small-latest",
            "codestral-latest"
        ]

    def get_metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            display_name="Mistral AI",
            description="European AI leader with powerful multilingual models and GDPR compliance",
            logo_url="https://mistral.ai/images/logo_hubc88c4ece131b91c7cb753f40e9e1cc5_2589_256x0_resize_q97_h2_lanczos_3.webp",
            website_url="https://mistral.ai/",
            requires_api_key=True,
            requires_base_url=False
        )


# Auto-register this provider
def register():
    from src.providers import ProviderRegistry
    ProviderRegistry.register(MistralProvider)
