"""
LLM Microservice Settings Configuration
Uses Pydantic Settings for environment variable management and validation
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator, model_validator
from typing import List, Optional, Union
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""

    # =========================================================================
    # Service Configuration
    # =========================================================================
    SERVICE_NAME: str = "llm_hub"
    SERVICE_VERSION: str = "1.0.0"
    LOG_LEVEL: str = "info"

    # =========================================================================
    # Database Configuration (TimescaleDB)
    # =========================================================================
    DATABASE_URL: str
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    DB_POOL_TIMEOUT: int = 30
    DB_ECHO: bool = False  # Set to True to log SQL queries

    # =========================================================================
    # Redis Configuration
    # =========================================================================
    REDIS_URL: str = "redis://localhost:6379"
    REDIS_DB: int = 0
    REDIS_CACHE_TTL: int = 3600  # 1 hour default cache TTL

    # =========================================================================
    # LLM Provider API Keys
    # =========================================================================
    OPENAI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None
    GOOGLE_API_KEY: Optional[str] = None
    MISTRAL_API_KEY: Optional[str] = None
    COHERE_API_KEY: Optional[str] = None
    RUNWAY_API_KEY: Optional[str] = None
    FAL_KEY: Optional[str] = None  # Fal.ai API key (provides access to Pika Labs models)
    ELEVENLABS_API_KEY: Optional[str] = None  # ElevenLabs text-to-speech
    VOYAGE_API_KEY: Optional[str] = None  # VoyageAI embeddings and reranking
    ASSEMBLYAI_API_KEY: Optional[str] = None  # AssemblyAI speech-to-text and audio intelligence
    DEEPGRAM_API_KEY: Optional[str] = None  # Deepgram ultra-fast speech-to-text with streaming
    PERSPECTIVE_API_KEY: Optional[str] = None  # Google Perspective API for content moderation and toxicity detection
    OLLAMA_BASE_URL: Optional[str] = "http://localhost:11434"

    # =========================================================================
    # LLM Provider Configuration
    # =========================================================================
    DEFAULT_PROVIDER: str = "claude"
    DEFAULT_MODEL: str = "claude-3-5-sonnet-20241022"
    DEFAULT_MAX_TOKENS: int = 4096
    DEFAULT_TEMPERATURE: float = 0.7
    DEFAULT_TIMEOUT: int = 60  # seconds
    MAX_RETRIES: int = 3
    RETRY_DELAY: float = 1.0  # seconds

    # =========================================================================
    # MinIO Configuration (for image storage)
    # =========================================================================
    MINIO_ENDPOINT: str = "localhost"
    MINIO_PORT: int = 9000
    MINIO_ACCESS_KEY: str = "minioadmin"
    MINIO_SECRET_KEY: str = "minioadmin"
    MINIO_USE_SSL: bool = False
    MINIO_BUCKET: str = "recloud-uploads"
    MINIO_REGION: str = "us-east-1"

    # =========================================================================
    # CORS Configuration
    # =========================================================================
    CORS_ORIGINS: Union[str, List[str]] = [
        "http://localhost:3000",
        "http://localhost:5173",
    ]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: List[str] = ["*"]
    CORS_ALLOW_HEADERS: List[str] = ["*"]

    # =========================================================================
    # Rate Limiting
    # =========================================================================
    DEFAULT_RATE_LIMIT: int = 100  # requests per minute per client
    RATE_LIMIT_WINDOW: int = 60  # seconds

    # =========================================================================
    # Cost Tracking (USD per 1K tokens)
    # =========================================================================
    # OpenAI Pricing
    OPENAI_GPT4_INPUT_COST: float = 0.03
    OPENAI_GPT4_OUTPUT_COST: float = 0.06
    OPENAI_GPT4_TURBO_INPUT_COST: float = 0.01
    OPENAI_GPT4_TURBO_OUTPUT_COST: float = 0.03
    OPENAI_GPT35_INPUT_COST: float = 0.0015
    OPENAI_GPT35_OUTPUT_COST: float = 0.002

    # Anthropic Pricing
    ANTHROPIC_CLAUDE_OPUS_INPUT_COST: float = 0.015
    ANTHROPIC_CLAUDE_OPUS_OUTPUT_COST: float = 0.075
    ANTHROPIC_CLAUDE_SONNET_INPUT_COST: float = 0.003
    ANTHROPIC_CLAUDE_SONNET_OUTPUT_COST: float = 0.015
    ANTHROPIC_CLAUDE_HAIKU_INPUT_COST: float = 0.00025
    ANTHROPIC_CLAUDE_HAIKU_OUTPUT_COST: float = 0.00125

    # Groq Pricing (much cheaper, faster inference)
    GROQ_MIXTRAL_INPUT_COST: float = 0.00027
    GROQ_MIXTRAL_OUTPUT_COST: float = 0.00027
    GROQ_LLAMA_INPUT_COST: float = 0.00007
    GROQ_LLAMA_OUTPUT_COST: float = 0.00007

    # DALL-E Pricing
    DALLE_STANDARD_1024_COST: float = 0.04
    DALLE_STANDARD_1792_COST: float = 0.08
    DALLE_HD_1024_COST: float = 0.08
    DALLE_HD_1792_COST: float = 0.12

    # =========================================================================
    # API Documentation
    # =========================================================================
    DOCS_URL: str = "/docs"
    REDOC_URL: str = "/redoc"
    OPENAPI_URL: str = "/openapi.json"

    # =========================================================================
    # Model Validators
    # =========================================================================
    @model_validator(mode='before')
    @classmethod
    def parse_string_fields(cls, values):
        """Parse CORS_ORIGINS from comma-separated string if needed"""
        if isinstance(values, dict):
            if 'CORS_ORIGINS' in values and isinstance(values['CORS_ORIGINS'], str):
                values['CORS_ORIGINS'] = [origin.strip() for origin in values['CORS_ORIGINS'].split(',')]
        return values

    # =========================================================================
    # Pydantic Settings Configuration
    # =========================================================================
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore"  # Ignore extra fields in .env
    )

    # =========================================================================
    # Helper Methods
    # =========================================================================

    def get_cost_per_1k_tokens(self, provider: str, model: str, token_type: str) -> float:
        """
        Get the cost per 1K tokens for a specific provider/model combination

        Args:
            provider: 'claude', 'openai', 'groq'
            model: Model identifier
            token_type: 'input' or 'output'

        Returns:
            Cost in USD per 1K tokens
        """
        provider = provider.lower()
        token_type = token_type.lower()

        # OpenAI pricing
        if provider == "openai":
            if "gpt-4-turbo" in model or "gpt-4-1106" in model:
                return self.OPENAI_GPT4_TURBO_INPUT_COST if token_type == "input" else self.OPENAI_GPT4_TURBO_OUTPUT_COST
            elif "gpt-4" in model:
                return self.OPENAI_GPT4_INPUT_COST if token_type == "input" else self.OPENAI_GPT4_OUTPUT_COST
            elif "gpt-3.5" in model:
                return self.OPENAI_GPT35_INPUT_COST if token_type == "input" else self.OPENAI_GPT35_OUTPUT_COST

        # Anthropic pricing
        elif provider == "claude":
            if "opus" in model:
                return self.ANTHROPIC_CLAUDE_OPUS_INPUT_COST if token_type == "input" else self.ANTHROPIC_CLAUDE_OPUS_OUTPUT_COST
            elif "sonnet" in model:
                return self.ANTHROPIC_CLAUDE_SONNET_INPUT_COST if token_type == "input" else self.ANTHROPIC_CLAUDE_SONNET_OUTPUT_COST
            elif "haiku" in model:
                return self.ANTHROPIC_CLAUDE_HAIKU_INPUT_COST if token_type == "input" else self.ANTHROPIC_CLAUDE_HAIKU_OUTPUT_COST

        # Groq pricing
        elif provider == "groq":
            if "mixtral" in model:
                return self.GROQ_MIXTRAL_INPUT_COST if token_type == "input" else self.GROQ_MIXTRAL_OUTPUT_COST
            elif "llama" in model:
                return self.GROQ_LLAMA_INPUT_COST if token_type == "input" else self.GROQ_LLAMA_OUTPUT_COST

        # Default fallback
        return 0.01 if token_type == "input" else 0.03

    def get_dalle_cost(self, size: str, quality: str = "standard") -> float:
        """
        Get the cost for DALL-E image generation

        Args:
            size: Image size (1024x1024, 1792x1024, 1024x1792)
            quality: 'standard' or 'hd'

        Returns:
            Cost in USD per image
        """
        if quality == "hd":
            return self.DALLE_HD_1792_COST if "1792" in size else self.DALLE_HD_1024_COST
        else:
            return self.DALLE_STANDARD_1792_COST if "1792" in size else self.DALLE_STANDARD_1024_COST

    @property
    def minio_endpoint_url(self) -> str:
        """Get full MinIO endpoint URL"""
        protocol = "https" if self.MINIO_USE_SSL else "http"
        return f"{protocol}://{self.MINIO_ENDPOINT}:{self.MINIO_PORT}"


@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance
    Uses lru_cache to ensure settings are loaded only once
    """
    return Settings()


# Create global settings instance
settings = get_settings()
