"""
Cohere Provider
Enterprise LLM with excellent RAG capabilities and GDPR compliance
"""

from typing import List, Dict, Any, Optional
import cohere
from src.providers.base import BaseProvider, LLMResponse, ProviderConfig, ProviderMetadata
from src.utils.logger import logger


class CohereProvider(BaseProvider):
    """Cohere provider implementation"""

    @property
    def provider_name(self) -> str:
        return "cohere"

    def is_available(self) -> bool:
        return bool(self.config.api_key)

    def _get_client(self) -> cohere.Client:
        """Lazy client initialization"""
        if not self._client and self.config.api_key:
            self._client = cohere.Client(api_key=self.config.api_key)
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
        """Call Cohere API"""
        if not self.is_available():
            raise ValueError("Cohere API key not configured")

        client = self._get_client()

        try:
            # Cohere uses chat API with message history
            chat_history = []
            user_message = ""

            # Process messages
            for msg in messages:
                role = msg["role"]
                content = msg["content"]

                if role == "system":
                    # System messages handled via preamble parameter
                    continue
                elif role == "user":
                    user_message = content
                elif role == "assistant":
                    chat_history.append({
                        "role": "CHATBOT",
                        "message": content
                    })

            # Prepare chat parameters
            chat_params = {
                "message": user_message or messages[-1]["content"],
                "model": model,
                "temperature": temperature if temperature is not None else 0.7,
                "chat_history": chat_history if chat_history else None,
            }

            # Add system prompt as preamble if provided
            if system_prompt:
                chat_params["preamble"] = system_prompt

            # Add max_tokens if specified
            if max_tokens:
                chat_params["max_tokens"] = max_tokens

            # Call Cohere Chat API
            response = client.chat(**chat_params)

            # Extract response content
            content = response.text

            # Get token counts from response
            # Cohere returns token counts in meta field
            input_tokens = 0
            output_tokens = 0

            if hasattr(response, 'meta') and response.meta:
                if hasattr(response.meta, 'billed_units'):
                    input_tokens = getattr(response.meta.billed_units, 'input_tokens', 0)
                    output_tokens = getattr(response.meta.billed_units, 'output_tokens', 0)

            # Calculate cost
            cost_usd = self.calculate_cost(model, input_tokens, output_tokens)

            return LLMResponse(
                content=content,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost_usd,
                provider_metadata={
                    "model": model,
                    "finish_reason": getattr(response, 'finish_reason', None),
                    "generation_id": getattr(response, 'generation_id', None)
                }
            )

        except Exception as e:
            logger.error(f"Cohere API error: {str(e)}")
            raise

    def get_models(self) -> List[str]:
        return [
            "command-r-plus",
            "command-r",
            "command",
            "command-light"
        ]

    def get_metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            display_name="Cohere",
            description="Enterprise AI with excellent RAG capabilities, multilingual support, and GDPR compliance",
            logo_url="https://cohere.com/favicon.ico",
            website_url="https://cohere.com",
            requires_api_key=True,
            requires_base_url=False
        )


# Auto-register this provider
def register():
    from src.providers import ProviderRegistry
    ProviderRegistry.register(CohereProvider)
