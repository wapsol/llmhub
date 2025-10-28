"""
Pydantic Models for Request/Response Validation
Used by FastAPI for automatic validation and documentation
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from enum import Enum


# ============================================================================
# Enums
# ============================================================================

class LLMProvider(str, Enum):
    """Supported LLM providers"""
    CLAUDE = "claude"
    OPENAI = "openai"
    GROQ = "groq"


class ContentType(str, Enum):
    """Content types for generation"""
    WHITEPAPER = "whitepaper"
    LINKEDIN_POST = "linkedin_post"
    ONE_PAGER = "1pager"
    EMAIL = "email"
    TRANSLATION = "translation"


class PromptStatus(str, Enum):
    """Prompt version statuses"""
    DRAFT = "draft"
    TESTING = "testing"
    PRODUCTION = "production"
    ARCHIVED = "archived"


# ============================================================================
# Content Generation Schemas
# ============================================================================

class ContentGenerationRequest(BaseModel):
    """Request schema for content generation"""
    prompt: str = Field(..., min_length=10, max_length=10000, description="Content generation prompt")
    provider: LLMProvider = Field(default=LLMProvider.CLAUDE, description="LLM provider to use")
    model: str = Field(default="claude-3-5-sonnet-20241022", description="Specific model to use")
    languages: List[str] = Field(default=["en"], description="Target languages (en, de, fr, it)")
    template_id: Optional[UUID] = Field(None, description="Optional prompt template to use")
    variables: Optional[Dict[str, Any]] = Field(None, description="Variables for template substitution")
    max_tokens: Optional[int] = Field(4096, ge=100, le=16000, description="Maximum tokens to generate")
    temperature: Optional[float] = Field(0.7, ge=0.0, le=2.0, description="Temperature for generation")

    class Config:
        json_schema_extra = {
            "example": {
                "prompt": "Create a whitepaper about cloud security for financial institutions",
                "provider": "claude",
                "model": "claude-3-5-sonnet-20241022",
                "languages": ["en", "de"],
                "max_tokens": 4096,
                "temperature": 0.7
            }
        }


class TranslationContent(BaseModel):
    """Content fields to translate"""
    title: Optional[str] = None
    body: Optional[str] = None
    meta_title: Optional[str] = None
    meta_description: Optional[str] = None
    meta_keywords: Optional[str] = None


class TranslationRequest(BaseModel):
    """Request schema for content translation"""
    content: TranslationContent = Field(..., description="Content to translate")
    source_language: str = Field(..., description="Source language code (en, de, fr, it)")
    target_languages: List[str] = Field(..., description="Target language codes")
    provider: LLMProvider = Field(default=LLMProvider.CLAUDE)
    model: str = Field(default="claude-3-5-sonnet-20241022")

    class Config:
        json_schema_extra = {
            "example": {
                "content": {
                    "title": "Cloud Security for Financial Services",
                    "body": "# Introduction\nCloud security is critical...",
                    "meta_description": "Enterprise cloud security solutions"
                },
                "source_language": "en",
                "target_languages": ["de", "fr", "it"],
                "provider": "claude"
            }
        }


class ContentGenerationResponse(BaseModel):
    """Response schema for content generation"""
    success: bool
    content: Dict[str, Any]  # Language code -> generated content
    tokens_used: int
    cost_usd: float
    generation_time_ms: int
    provider: str
    model: str
    log_id: UUID


# ============================================================================
# Image Generation Schemas
# ============================================================================

class ImageGenerationRequest(BaseModel):
    """Request schema for image generation (DALL-E 3)"""
    prompt: str = Field(..., min_length=10, max_length=4000, description="Image generation prompt")
    size: str = Field(default="1024x1024", description="Image size (1024x1024, 1792x1024, 1024x1792)")
    quality: str = Field(default="standard", description="Image quality (standard, hd)")
    style: str = Field(default="vivid", description="Image style (vivid, natural)")
    upload_to_minio: bool = Field(default=True, description="Upload to MinIO storage")

    @validator('size')
    def validate_size(cls, v):
        valid_sizes = ["1024x1024", "1792x1024", "1024x1792"]
        if v not in valid_sizes:
            raise ValueError(f"Size must be one of {valid_sizes}")
        return v

    @validator('quality')
    def validate_quality(cls, v):
        if v not in ["standard", "hd"]:
            raise ValueError("Quality must be 'standard' or 'hd'")
        return v

    @validator('style')
    def validate_style(cls, v):
        if v not in ["vivid", "natural"]:
            raise ValueError("Style must be 'vivid' or 'natural'")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "prompt": "A futuristic data center with glowing servers and holographic interfaces",
                "size": "1024x1024",
                "quality": "hd",
                "style": "vivid"
            }
        }


class ImageGenerationResponse(BaseModel):
    """Response schema for image generation"""
    success: bool
    image_url: str  # Primary URL (MinIO if available, else OpenAI)
    openai_url: str  # Temporary OpenAI URL (expires in 1 hour)
    permanent_url: Optional[str]  # MinIO permanent URL
    revised_prompt: Optional[str]  # DALL-E's interpretation of the prompt
    cost_usd: float
    generation_time_ms: int
    size: str
    quality: str
    log_id: UUID


class ImageEditRequest(BaseModel):
    """Request schema for image editing (DALL-E 2)"""
    image_url: str = Field(..., description="URL of the image to edit")
    mask_url: Optional[str] = Field(None, description="URL of the mask image (transparent areas will be edited)")
    prompt: str = Field(..., min_length=10, max_length=1000, description="Description of the desired edit")
    size: str = Field(default="1024x1024", description="Output size (256x256, 512x512, 1024x1024)")

    @validator('size')
    def validate_size(cls, v):
        valid_sizes = ["256x256", "512x512", "1024x1024"]
        if v not in valid_sizes:
            raise ValueError(f"Size must be one of {valid_sizes}")
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "image_url": "https://example.com/datacenter.png",
                "prompt": "Add more servers with blue lighting",
                "size": "1024x1024"
            }
        }


# ============================================================================
# Prompt Library Schemas
# ============================================================================

class PromptTemplateCreate(BaseModel):
    """Schema for creating a new prompt template"""
    template_name: str = Field(..., min_length=3, max_length=255)
    template_type: ContentType
    description: Optional[str] = None
    system_prompt: str = Field(..., min_length=10)
    user_prompt_template: str = Field(..., min_length=10)
    variables: Optional[Dict[str, Any]] = None
    output_config: Optional[Dict[str, Any]] = None
    is_public: bool = Field(default=False)


class PromptTemplateUpdate(BaseModel):
    """Schema for updating a prompt template"""
    template_name: Optional[str] = None
    description: Optional[str] = None
    system_prompt: Optional[str] = None
    user_prompt_template: Optional[str] = None
    variables: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class PromptTemplateResponse(BaseModel):
    """Response schema for prompt template"""
    template_id: UUID
    template_name: str
    template_type: str
    description: Optional[str]
    variables: Optional[Dict[str, Any]]
    usage_count: int
    success_rate: Optional[float]
    is_public: bool
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ============================================================================
# Billing Schemas
# ============================================================================

class UsageReportRequest(BaseModel):
    """Request schema for usage report"""
    start_date: datetime
    end_date: datetime
    group_by: str = Field(default="day", description="Group by: hour, day, month")


class UsageSummary(BaseModel):
    """Usage summary for a time period"""
    period: datetime
    call_count: int
    total_tokens: int
    total_cost_usd: float
    avg_generation_time_ms: float
    success_rate: float


class UsageReportResponse(BaseModel):
    """Response schema for usage report"""
    client_name: str
    start_date: datetime
    end_date: datetime
    summary: List[UsageSummary]
    total_cost_usd: float
    total_calls: int


# ============================================================================
# Health Check Schemas
# ============================================================================

class HealthCheckResponse(BaseModel):
    """Health check response"""
    status: str
    timestamp: datetime
    version: str
    uptime: Optional[float] = None


class DetailedHealthCheckResponse(BaseModel):
    """Detailed health check with dependency status"""
    status: str
    timestamp: datetime
    checks: Dict[str, str]  # service_name -> status


# ============================================================================
# Error Response Schema
# ============================================================================

class ErrorResponse(BaseModel):
    """Standard error response"""
    success: bool = False
    error: Dict[str, Any]

    class Config:
        json_schema_extra = {
            "example": {
                "success": False,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "Invalid request parameters",
                    "details": []
                }
            }
        }
