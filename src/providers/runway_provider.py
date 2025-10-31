"""
RunwayML Video Generation Provider
Supports Gen-3 and Gen-4 models for text-to-video and image-to-video generation
"""

from typing import List, Dict, Any, Optional
import asyncio
import time
from runwayml import AsyncRunwayML
from src.providers.base import BaseProvider, LLMResponse, ProviderConfig, ProviderMetadata
from src.utils.logger import logger


class RunwayProvider(BaseProvider):
    """
    RunwayML provider for video generation

    Supported models:
    - gen4_turbo (default): Fast, high-quality (5 credits/sec)
    - gen4_aleph: Highest quality (15 credits/sec)
    - gen3_turbo: Fast, good quality (5 credits/sec)
    """

    # Credit costs per second of video
    MODEL_CREDITS = {
        "gen4_turbo": 5,
        "gen4_aleph": 15,
        "gen3_turbo": 5,
        "gen3_alpha": 10
    }

    CREDIT_COST_USD = 0.01  # $0.01 per credit

    # Aspect ratio mapping
    ASPECT_RATIOS = {
        "16:9": "1280:720",
        "9:16": "720:1280",
        "1:1": "1024:1024",
        "4:3": "1024:768"
    }

    @property
    def provider_name(self) -> str:
        return "runway"

    def is_available(self) -> bool:
        return bool(self.config.api_key)

    def _get_client(self) -> AsyncRunwayML:
        """Lazy client initialization"""
        if not self._client and self.config.api_key:
            self._client = AsyncRunwayML(api_key=self.config.api_key)
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
        """
        Generate video using RunwayML API

        Note: Runway is video-focused, so it doesn't use traditional text messages.
        Instead, kwargs should contain video generation parameters:
        - prompt: Text prompt for generation
        - prompt_image: Optional image URL for image-to-video
        - duration: Video duration in seconds (default: 5)
        - ratio: Aspect ratio (default: "1280:720" = 16:9)
        - operation: "generate", "extend", or "remix" (default: "generate")
        - video_url: Required for extend/remix operations
        """
        if not self.is_available():
            raise ValueError("RunwayML API key not configured")

        client = self._get_client()

        # Extract video-specific parameters
        prompt = kwargs.get("prompt", "")
        prompt_image = kwargs.get("prompt_image")
        duration = kwargs.get("duration", 5)
        ratio = kwargs.get("ratio", "1280:720")
        operation = kwargs.get("operation", "generate")
        video_url = kwargs.get("video_url")

        # Validate duration (RunwayML supports 5 or 10 seconds)
        if duration not in [5, 10]:
            logger.warning(f"Duration {duration} not standard. Rounding to nearest (5 or 10)")
            duration = 5 if duration <= 7 else 10

        try:
            # Determine operation type and call appropriate endpoint
            if operation == "generate":
                if prompt_image:
                    # Image-to-video generation
                    logger.info(f"Starting image-to-video generation with model {model}")
                    task = await client.image_to_video.create(
                        model=model,
                        prompt_image=prompt_image,
                        prompt_text=prompt,
                        duration=duration,
                        ratio=ratio
                    )
                else:
                    # Text-to-video generation
                    # Note: RunwayML Gen-4 primarily does image-to-video
                    # For pure text-to-video, we'd need to generate an image first
                    # or use a different approach
                    raise ValueError(
                        "RunwayML Gen-4 requires an image for video generation. "
                        "Use 'prompt_image' parameter or generate an image first."
                    )

            elif operation == "extend":
                if not video_url:
                    raise ValueError("video_url required for extend operation")

                logger.info(f"Starting video extension with model {model}")
                # RunwayML doesn't have a direct extend endpoint in the SDK yet
                # This would need to use the video-to-video endpoint with specific parameters
                raise NotImplementedError(
                    "Video extension will be implemented when RunwayML SDK adds extend support"
                )

            elif operation == "remix":
                if not video_url:
                    raise ValueError("video_url required for remix operation")

                logger.info(f"Starting video remix with model {model}")
                # Video-to-video transformation
                raise NotImplementedError(
                    "Video remix will be implemented when RunwayML SDK adds video-to-video support"
                )

            else:
                raise ValueError(f"Unknown operation: {operation}")

            # Poll for task completion
            logger.info(f"Polling task {task.id} for completion...")
            completed_task = await self._poll_task_completion(client, task.id)

            # Extract video URL from completed task
            video_url = self._extract_video_url(completed_task)

            # Calculate cost based on duration and model
            cost_usd = self._calculate_video_cost(model, duration)

            # For video generation, "tokens" don't apply in the same way
            # We'll use duration as a proxy (1 second = 100 "tokens" for tracking)
            pseudo_tokens = duration * 100

            return LLMResponse(
                content=video_url,
                input_tokens=pseudo_tokens,  # Duration-based proxy
                output_tokens=0,
                cost_usd=cost_usd,
                provider_metadata={
                    "model": model,
                    "task_id": task.id,
                    "duration": duration,
                    "ratio": ratio,
                    "operation": operation
                }
            )

        except Exception as e:
            logger.error(f"RunwayML API error: {str(e)}")
            raise

    async def _poll_task_completion(
        self,
        client: AsyncRunwayML,
        task_id: str,
        max_wait_seconds: int = 300,
        poll_interval: float = 2.0
    ) -> Any:
        """
        Poll RunwayML task until completion

        Args:
            client: RunwayML client
            task_id: Task ID to poll
            max_wait_seconds: Maximum time to wait (default: 5 minutes)
            poll_interval: Seconds between polls (default: 2 seconds)

        Returns:
            Completed task object

        Raises:
            TimeoutError: If task doesn't complete in time
            Exception: If task fails
        """
        start_time = time.time()

        while True:
            elapsed = time.time() - start_time

            if elapsed > max_wait_seconds:
                raise TimeoutError(
                    f"Task {task_id} did not complete within {max_wait_seconds} seconds"
                )

            # Get task status
            task = await client.tasks.retrieve(task_id)

            logger.debug(f"Task {task_id} status: {task.status}")

            if task.status == "SUCCEEDED":
                logger.info(f"Task {task_id} completed successfully")
                return task

            elif task.status == "FAILED":
                error_msg = getattr(task, "failure_reason", "Unknown error")
                raise Exception(f"Task {task_id} failed: {error_msg}")

            elif task.status in ["PENDING", "RUNNING"]:
                # Still processing, wait and retry
                await asyncio.sleep(poll_interval)
                continue

            else:
                raise Exception(f"Unknown task status: {task.status}")

    def _extract_video_url(self, task: Any) -> str:
        """
        Extract video URL from completed task

        Args:
            task: Completed task object

        Returns:
            Video URL
        """
        # RunwayML returns output URLs in task.output
        if hasattr(task, "output") and task.output:
            # Output is typically a list of URLs
            if isinstance(task.output, list) and len(task.output) > 0:
                return task.output[0]
            elif isinstance(task.output, str):
                return task.output

        raise ValueError("Could not extract video URL from task output")

    def _calculate_video_cost(self, model: str, duration: int) -> float:
        """
        Calculate cost for video generation

        Args:
            model: Model identifier
            duration: Video duration in seconds

        Returns:
            Cost in USD
        """
        credits_per_second = self.MODEL_CREDITS.get(model, 5)  # Default to gen4_turbo rate
        total_credits = credits_per_second * duration
        cost_usd = total_credits * self.CREDIT_COST_USD
        return round(cost_usd, 4)

    def get_models(self) -> List[str]:
        return [
            "gen4_turbo",
            "gen4_aleph",
            "gen3_turbo",
            "gen3_alpha"
        ]

    def get_metadata(self) -> ProviderMetadata:
        return ProviderMetadata(
            display_name="RunwayML",
            description="Advanced AI video generation with Gen-3 and Gen-4 models. Text-to-video and image-to-video capabilities.",
            logo_url="https://runwayml.com/favicon.ico",
            website_url="https://runwayml.com",
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
        Override base calculate_cost since Runway uses duration-based pricing

        For Runway, input_tokens represents (duration_seconds * 100)
        This allows us to use the standard token-based cost tracking system
        """
        duration_seconds = input_tokens // 100
        return self._calculate_video_cost(model, duration_seconds)


# Auto-register this provider
def register():
    from src.providers import ProviderRegistry
    ProviderRegistry.register(RunwayProvider)
