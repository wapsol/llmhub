"""
Pika Labs Video Generation Provider (via Fal.ai)
Supports Pika v2.2 models for image-to-video generation
"""

from typing import List, Dict, Any, Optional
import os
import fal_client
from src.providers.base import BaseProvider, LLMResponse, ProviderConfig, ProviderMetadata
from src.utils.logger import logger


class PikaProvider(BaseProvider):
    """
    Pika Labs provider for video generation via Fal.ai

    Supported models:
    - pika-2.2-720p (default): 720p resolution ($0.20 per 5s video)
    - pika-2.2-1080p: 1080p resolution ($0.45 per 5s video)

    Note: Pika does not have a public API yet. This provider uses
    Fal.ai's hosted Pika models which provide official access.
    """

    # Fixed costs per video (Pika v2.2 pricing via Fal.ai)
    MODEL_COSTS = {
        "pika-2.2-720p": 0.20,   # $0.20 per 5-second video
        "pika-2.2-1080p": 0.45   # $0.45 per 5-second video
    }

    # Map our model names to Fal.ai endpoints
    FAL_ENDPOINTS = {
        "pika-2.2-720p": "fal-ai/pika/v2.2/image-to-video",
        "pika-2.2-1080p": "fal-ai/pika/v2.2/image-to-video"
    }

    # Resolution mapping
    RESOLUTIONS = {
        "pika-2.2-720p": "720p",
        "pika-2.2-1080p": "1080p"
    }

    @property
    def provider_name(self) -> str:
        return "pika"

    def is_available(self) -> bool:
        """Check if Fal.ai API key is configured"""
        return bool(self.config.api_key)

    def _configure_fal_client(self):
        """Configure fal_client with API key"""
        if self.config.api_key:
            # Set FAL_KEY environment variable for fal_client
            os.environ['FAL_KEY'] = self.config.api_key

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
        Generate video using Pika via Fal.ai

        Note: Pika is video-focused, so it doesn't use traditional text messages.
        Instead, kwargs should contain video generation parameters:
        - prompt: Text prompt for video generation
        - prompt_image: Image URL for image-to-video (REQUIRED)
        - duration: Video duration (default: 5 seconds, only 5s supported)
        - operation: "generate" (default)
        """
        if not self.is_available():
            raise ValueError("Fal.ai API key not configured (FAL_KEY required for Pika)")

        # Configure fal_client
        self._configure_fal_client()

        # Extract video-specific parameters
        prompt = kwargs.get("prompt", "")
        prompt_image = kwargs.get("prompt_image")
        duration = kwargs.get("duration", 5)
        operation = kwargs.get("operation", "generate")

        # Validate required parameters
        if not prompt_image:
            raise ValueError(
                "Pika requires 'prompt_image' URL for video generation. "
                "Provide an image URL in the request."
            )

        # Pika v2.2 only supports 5-second videos
        if duration != 5:
            logger.warning(f"Pika v2.2 only supports 5-second videos. Requested {duration}s, using 5s.")
            duration = 5

        # Get resolution for this model
        resolution = self.RESOLUTIONS.get(model, "720p")

        # Get Fal.ai endpoint for this model
        fal_endpoint = self.FAL_ENDPOINTS.get(model)
        if not fal_endpoint:
            raise ValueError(f"Unknown Pika model: {model}")

        try:
            logger.info(f"Starting Pika video generation: model={model}, resolution={resolution}")

            # Submit request to Fal.ai
            # Using submit method for async task with status updates
            handler = fal_client.submit(
                fal_endpoint,
                arguments={
                    "image_url": prompt_image,
                    "prompt": prompt,
                    "resolution": resolution
                }
            )

            # Poll for completion with status updates
            logger.info(f"Pika task submitted, polling for completion...")

            # Wait for result (this handles polling internally)
            result = handler.get()

            # Extract video URL from result
            video_url = result.get("video", {}).get("url")
            if not video_url:
                raise ValueError("No video URL in Pika response")

            # Calculate cost (fixed per video based on model)
            cost_usd = self.MODEL_COSTS.get(model, 0.20)

            # For billing tracking: use pseudo-tokens
            # Map cost to tokens: $0.01 = 100 tokens
            # So $0.20 = 2000 tokens, $0.45 = 4500 tokens
            pseudo_tokens = int(cost_usd * 10000)

            logger.info(
                f"Pika video generated successfully: resolution={resolution}, "
                f"cost=${cost_usd}, url={video_url[:50]}..."
            )

            return LLMResponse(
                content=video_url,
                input_tokens=pseudo_tokens,  # Cost-based proxy for billing
                output_tokens=0,
                cost_usd=cost_usd,
                provider_metadata={
                    "model": model,
                    "resolution": resolution,
                    "duration": duration,
                    "fal_endpoint": fal_endpoint
                }
            )

        except Exception as e:
            logger.error(f"Pika video generation failed: {str(e)}")
            raise Exception(f"Pika generation error: {str(e)}")

    def get_models(self) -> List[str]:
        return [
            "pika-2.2-720p",
            "pika-2.2-1080p"
        ]

    def get_metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            display_name="Pika Labs (via Fal.ai)",
            description="Advanced AI video generation with Pika v2.2. High-quality image-to-video with 720p and 1080p support. Powered by Fal.ai.",
            logo_url="https://pika.art/favicon.ico",
            website_url="https://pika.art",
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
        Override base calculate_cost since Pika uses fixed per-video pricing

        For Pika, input_tokens represents the cost in pseudo-tokens:
        - 2000 tokens = $0.20 (720p)
        - 4500 tokens = $0.45 (1080p)
        """
        # Convert tokens back to cost
        return input_tokens / 10000


# Auto-register this provider
def register():
    from src.providers import ProviderRegistry
    ProviderRegistry.register(PikaProvider)
