"""
LLM Core Service
Multi-provider LLM integration with cost tracking and error handling
"""

from typing import Dict, Any, Optional, List
import time
import asyncio
from anthropic import Anthropic, AsyncAnthropic
from openai import OpenAI, AsyncOpenAI
import httpx
import tiktoken

from src.config.settings import settings
from src.utils.logger import logger


class LLMCoreService:
    """Core service for LLM API calls with multi-provider support"""

    def __init__(self):
        # Initialize LLM clients
        self.anthropic_client = None
        self.openai_client = None
        self.groq_client = None

        # Initialize clients if API keys are available
        if settings.ANTHROPIC_API_KEY:
            self.anthropic_client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
            logger.info("Anthropic client initialized")

        if settings.OPENAI_API_KEY:
            self.openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
            logger.info("OpenAI client initialized")

        if settings.GROQ_API_KEY:
            # Groq uses OpenAI-compatible API
            self.groq_client = OpenAI(
                api_key=settings.GROQ_API_KEY,
                base_url="https://api.groq.com/openai/v1"
            )
            logger.info("Groq client initialized")

    async def call_llm(
        self,
        provider: str,
        model: str,
        messages: List[Dict[str, str]],
        max_tokens: Optional[int] = None,
        temperature: Optional[float] = None,
        system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Call LLM provider with unified interface

        Args:
            provider: 'claude', 'openai', or 'groq'
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

        max_tokens = max_tokens or settings.DEFAULT_MAX_TOKENS
        temperature = temperature if temperature is not None else settings.DEFAULT_TEMPERATURE

        # Route to appropriate provider
        try:
            if provider.lower() == "claude":
                result = await self._call_claude(model, messages, max_tokens, temperature, system_prompt)
            elif provider.lower() == "openai":
                result = await self._call_openai(model, messages, max_tokens, temperature, system_prompt)
            elif provider.lower() == "groq":
                result = await self._call_groq(model, messages, max_tokens, temperature, system_prompt)
            else:
                raise ValueError(f"Unsupported provider: {provider}")

            # Calculate generation time
            generation_time_ms = int((time.time() - start_time) * 1000)
            result["generation_time_ms"] = generation_time_ms

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

    async def _call_claude(
        self,
        model: str,
        messages: List[Dict[str, str]],
        max_tokens: int,
        temperature: float,
        system_prompt: Optional[str]
    ) -> Dict[str, Any]:
        """Call Anthropic Claude API"""
        if not self.anthropic_client:
            raise ValueError("Anthropic API key not configured")

        try:
            # Prepare messages for Claude format
            claude_messages = []
            for msg in messages:
                claude_messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })

            # Call Claude API
            response = self.anthropic_client.messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system_prompt if system_prompt else "",
                messages=claude_messages
            )

            # Extract response
            content = response.content[0].text if response.content else ""
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens

            # Calculate cost
            input_cost = (input_tokens / 1000) * settings.get_cost_per_1k_tokens("claude", model, "input")
            output_cost = (output_tokens / 1000) * settings.get_cost_per_1k_tokens("claude", model, "output")
            total_cost = input_cost + output_cost

            return {
                "content": content,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_usd": round(total_cost, 6)
            }

        except Exception as e:
            logger.error(f"Claude API error: {str(e)}")
            raise

    async def _call_openai(
        self,
        model: str,
        messages: List[Dict[str, str]],
        max_tokens: int,
        temperature: float,
        system_prompt: Optional[str]
    ) -> Dict[str, Any]:
        """Call OpenAI API"""
        if not self.openai_client:
            raise ValueError("OpenAI API key not configured")

        try:
            # Prepare messages
            openai_messages = []
            if system_prompt:
                openai_messages.append({"role": "system", "content": system_prompt})

            openai_messages.extend(messages)

            # Call OpenAI API
            response = self.openai_client.chat.completions.create(
                model=model,
                messages=openai_messages,
                max_tokens=max_tokens,
                temperature=temperature
            )

            # Extract response
            content = response.choices[0].message.content or ""
            input_tokens = response.usage.prompt_tokens
            output_tokens = response.usage.completion_tokens

            # Calculate cost
            input_cost = (input_tokens / 1000) * settings.get_cost_per_1k_tokens("openai", model, "input")
            output_cost = (output_tokens / 1000) * settings.get_cost_per_1k_tokens("openai", model, "output")
            total_cost = input_cost + output_cost

            return {
                "content": content,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_usd": round(total_cost, 6)
            }

        except Exception as e:
            logger.error(f"OpenAI API error: {str(e)}")
            raise

    async def _call_groq(
        self,
        model: str,
        messages: List[Dict[str, str]],
        max_tokens: int,
        temperature: float,
        system_prompt: Optional[str]
    ) -> Dict[str, Any]:
        """Call Groq API (OpenAI-compatible)"""
        if not self.groq_client:
            raise ValueError("Groq API key not configured")

        try:
            # Prepare messages
            groq_messages = []
            if system_prompt:
                groq_messages.append({"role": "system", "content": system_prompt})

            groq_messages.extend(messages)

            # Call Groq API (OpenAI-compatible interface)
            response = self.groq_client.chat.completions.create(
                model=model,
                messages=groq_messages,
                max_tokens=max_tokens,
                temperature=temperature
            )

            # Extract response
            content = response.choices[0].message.content or ""
            input_tokens = response.usage.prompt_tokens
            output_tokens = response.usage.completion_tokens

            # Calculate cost
            input_cost = (input_tokens / 1000) * settings.get_cost_per_1k_tokens("groq", model, "input")
            output_cost = (output_tokens / 1000) * settings.get_cost_per_1k_tokens("groq", model, "output")
            total_cost = input_cost + output_cost

            return {
                "content": content,
                "input_tokens": input_tokens,
                "output_tokens": output_tokens,
                "cost_usd": round(total_cost, 6)
            }

        except Exception as e:
            logger.error(f"Groq API error: {str(e)}")
            raise

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
            encoding = tiktoken.encoding_for_model(model)
            return len(encoding.encode(text))
        except Exception as e:
            logger.warning(f"Token counting error: {str(e)}, using fallback")
            # Fallback: rough estimate (1 token ~= 4 characters)
            return len(text) // 4


# Create global instance
llm_core = LLMCoreService()
