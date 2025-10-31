"""
Google Gemini Provider
"""

from typing import List, Dict, Any, Optional
import google.generativeai as genai
from src.providers.base import BaseProvider, LLMResponse, ProviderConfig, ProviderMetadata
from src.utils.logger import logger


class GeminiProvider(BaseProvider):
    """Google Gemini provider implementation"""

    @property
    def provider_name(self) -> str:
        return "google"

    def is_available(self) -> bool:
        return bool(self.config.api_key)

    def _get_client(self):
        """Lazy client initialization"""
        if not self._client and self.config.api_key:
            genai.configure(api_key=self.config.api_key)
            self._client = True  # Flag that we've configured
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
        """Call Gemini API"""
        if not self.is_available():
            raise ValueError("Google API key not configured")

        self._get_client()

        try:
            # Initialize model
            gemini_model = genai.GenerativeModel(
                model_name=model,
                system_instruction=system_prompt if system_prompt else None
            )

            # Convert messages to Gemini format
            # Gemini uses a chat history format
            chat_history = []
            user_message = None

            for msg in messages:
                role = msg["role"]
                content = msg["content"]

                if role == "system":
                    # System messages are handled via system_instruction
                    continue
                elif role == "user":
                    user_message = content
                    # Add to history (all but the last user message)
                    if len([m for m in messages if m["role"] == "user"]) > 1:
                        chat_history.append({
                            "role": "user",
                            "parts": [content]
                        })
                elif role == "assistant":
                    chat_history.append({
                        "role": "model",
                        "parts": [content]
                    })

            # Configure generation settings
            generation_config = genai.GenerationConfig(
                max_output_tokens=max_tokens or 4096,
                temperature=temperature if temperature is not None else 0.7,
            )

            # Start chat or generate content
            if chat_history:
                chat = gemini_model.start_chat(history=chat_history)
                response = chat.send_message(
                    user_message or messages[-1]["content"],
                    generation_config=generation_config
                )
            else:
                response = gemini_model.generate_content(
                    user_message or messages[-1]["content"],
                    generation_config=generation_config
                )

            # Extract response content
            content = response.text

            # Get token counts from response metadata
            input_tokens = 0
            output_tokens = 0

            if hasattr(response, 'usage_metadata'):
                input_tokens = response.usage_metadata.prompt_token_count or 0
                output_tokens = response.usage_metadata.candidates_token_count or 0

            # Calculate cost
            cost_usd = self.calculate_cost(model, input_tokens, output_tokens)

            return LLMResponse(
                content=content,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost_usd,
                provider_metadata={
                    "model": model,
                    "finish_reason": response.candidates[0].finish_reason.name if response.candidates else None
                }
            )

        except Exception as e:
            logger.error(f"Gemini API error: {str(e)}")
            raise

    def get_models(self) -> List[str]:
        return [
            "gemini-1.5-pro",
            "gemini-1.5-flash",
            "gemini-1.0-pro"
        ]

    def get_metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            display_name="Google Gemini",
            description="Google's multimodal AI models with long context windows and strong reasoning",
            logo_url="https://www.gstatic.com/lamda/images/gemini_sparkle_v002_d4735304ff6292a690345.svg",
            website_url="https://ai.google.dev/",
            requires_api_key=True,
            requires_base_url=False
        )


# Auto-register this provider
def register():
    from src.providers import ProviderRegistry
    ProviderRegistry.register(GeminiProvider)
