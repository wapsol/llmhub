"""
Anthropic Claude Provider
"""

from typing import List, Dict, Any, Optional
from anthropic import Anthropic
from src.providers.base import BaseProvider, LLMResponse, ProviderConfig, ProviderMetadata
from src.utils.logger import logger


class AnthropicProvider(BaseProvider):
    """Claude provider implementation"""

    @property
    def provider_name(self) -> str:
        return "claude"

    def is_available(self) -> bool:
        return bool(self.config.api_key)

    def _get_client(self) -> Anthropic:
        """Lazy client initialization"""
        if not self._client and self.config.api_key:
            self._client = Anthropic(api_key=self.config.api_key)
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
        """Call Claude API"""
        if not self.is_available():
            raise ValueError("Anthropic API key not configured")

        client = self._get_client()

        # Format messages for Claude
        claude_messages = [
            {"role": msg["role"], "content": msg["content"]}
            for msg in messages
        ]

        # Call API
        response = client.messages.create(
            model=model,
            max_tokens=max_tokens or 4096,
            temperature=temperature if temperature is not None else 0.7,
            system=system_prompt or "",
            messages=claude_messages,
            **kwargs
        )

        # Parse response
        content = response.content[0].text if response.content else ""
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens

        # Calculate cost
        cost_usd = self.calculate_cost(model, input_tokens, output_tokens)

        return LLMResponse(
            content=content,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cost_usd=cost_usd,
            provider_metadata={
                "model": response.model,
                "stop_reason": response.stop_reason
            }
        )

    def get_models(self) -> List[str]:
        return [
            "claude-3-5-sonnet-20241022",
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-3-haiku-20240307"
        ]

    def get_metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            display_name="Anthropic Claude",
            description="Advanced AI assistant with 200K context window and superior reasoning capabilities",
            logo_url="https://www.anthropic.com/images/icons/safari-pinned-tab.svg",
            website_url="https://www.anthropic.com",
            requires_api_key=True,
            requires_base_url=False
        )


# Auto-register this provider
def register():
    from src.providers import ProviderRegistry
    ProviderRegistry.register(AnthropicProvider)
