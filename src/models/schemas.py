"""
Pydantic Models for Request/Response Validation
Used by FastAPI for automatic validation and documentation
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Union
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
    OLLAMA = "ollama"
    GOOGLE = "google"
    MISTRAL = "mistral"
    COHERE = "cohere"


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


# ============================================================================
# API v2 Schemas - Provider & Model Agnostic
# ============================================================================

class V2BaseRequest(BaseModel):
    """Base request schema for all v2 endpoints with optional provider override"""
    provider: Optional[str] = Field(None, description="Optional provider override (claude, openai, groq, etc.)")
    model: Optional[str] = Field(None, description="Optional model override")
    max_tokens: Optional[int] = Field(None, ge=100, le=16000, description="Maximum tokens to generate")
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0, description="Temperature for generation")


class V2BaseResponse(BaseModel):
    """Base response schema for all v2 endpoints"""
    success: bool
    content: Any
    provider_used: str
    model_used: str
    tokens_used: int
    cost_usd: float
    generation_time_ms: int
    log_id: UUID


# ============================================================================
# V2 Text Operations Schemas
# ============================================================================

class V2TextGenerateRequest(V2BaseRequest):
    """Generate text content from prompt"""
    prompt: str = Field(..., min_length=1, max_length=50000, description="Text generation prompt")
    system_prompt: Optional[str] = Field(None, description="Optional system prompt for context")

    class Config:
        json_schema_extra = {
            "example": {
                "prompt": "Write a blog post about AI in healthcare",
                "system_prompt": "You are a healthcare technology expert",
                "max_tokens": 2000,
                "temperature": 0.7
            }
        }


class V2TextTranslateRequest(V2BaseRequest):
    """Translate text between languages"""
    text: str = Field(..., min_length=1, max_length=50000)
    source_language: str = Field(..., description="Source language code (e.g., 'en', 'de', 'fr')")
    target_language: str = Field(..., description="Target language code")

    class Config:
        json_schema_extra = {
            "example": {
                "text": "Hello, how are you today?",
                "source_language": "en",
                "target_language": "de"
            }
        }


class V2TextSummarizeRequest(V2BaseRequest):
    """Summarize long text"""
    text: str = Field(..., min_length=100, max_length=100000)
    summary_length: Optional[str] = Field("medium", description="short, medium, or long")

    class Config:
        json_schema_extra = {
            "example": {
                "text": "Long article text here...",
                "summary_length": "short"
            }
        }


class V2TextRewriteRequest(V2BaseRequest):
    """Rewrite/paraphrase text"""
    text: str = Field(..., min_length=1, max_length=50000)
    style: Optional[str] = Field(None, description="Target style (formal, casual, professional, etc.)")

    class Config:
        json_schema_extra = {
            "example": {
                "text": "This is some text to rewrite",
                "style": "professional"
            }
        }


class V2TextExpandRequest(V2BaseRequest):
    """Expand brief text into detailed content"""
    text: str = Field(..., min_length=1, max_length=10000)
    target_length: Optional[int] = Field(None, description="Approximate target word count")

    class Config:
        json_schema_extra = {
            "example": {
                "text": "AI is transforming healthcare",
                "target_length": 500
            }
        }


class V2TextCondenseRequest(V2BaseRequest):
    """Condense long text to key points"""
    text: str = Field(..., min_length=100, max_length=100000)
    num_points: Optional[int] = Field(5, ge=1, le=20, description="Number of key points")

    class Config:
        json_schema_extra = {
            "example": {
                "text": "Long article text here...",
                "num_points": 5
            }
        }


class V2TextAnalyzeRequest(V2BaseRequest):
    """Analyze text (sentiment, tone, etc.)"""
    text: str = Field(..., min_length=1, max_length=50000)
    analysis_types: List[str] = Field(default=["sentiment", "tone"], description="Types of analysis to perform")

    class Config:
        json_schema_extra = {
            "example": {
                "text": "I absolutely love this product! It's amazing!",
                "analysis_types": ["sentiment", "tone", "emotion"]
            }
        }


class V2TextClassifyRequest(V2BaseRequest):
    """Classify text into categories"""
    text: str = Field(..., min_length=1, max_length=50000)
    categories: List[str] = Field(..., description="List of possible categories")

    class Config:
        json_schema_extra = {
            "example": {
                "text": "This movie was fantastic! Great acting and plot.",
                "categories": ["positive review", "negative review", "neutral review"]
            }
        }


class V2TextExtractRequest(V2BaseRequest):
    """Extract entities, keywords, or structured data"""
    text: str = Field(..., min_length=1, max_length=50000)
    extract_types: List[str] = Field(default=["entities", "keywords"], description="What to extract")

    class Config:
        json_schema_extra = {
            "example": {
                "text": "Apple Inc. announced a new iPhone in Cupertino on September 12th.",
                "extract_types": ["entities", "dates", "keywords"]
            }
        }


class V2TextCompareRequest(V2BaseRequest):
    """Compare multiple texts"""
    texts: List[str] = Field(..., min_items=2, max_items=10, description="Texts to compare")
    comparison_aspects: Optional[List[str]] = Field(None, description="Specific aspects to compare")

    class Config:
        json_schema_extra = {
            "example": {
                "texts": [
                    "This product is great!",
                    "This product is terrible!"
                ],
                "comparison_aspects": ["sentiment", "tone", "key_themes"]
            }
        }


# ============================================================================
# V2 Document Operations Schemas
# ============================================================================

class V2DocumentParseRequest(V2BaseRequest):
    """Parse document structure"""
    document: str = Field(..., description="Document content")
    parse_elements: Optional[List[str]] = Field(default=["headings", "sections", "tables"], description="Elements to parse")

    class Config:
        json_schema_extra = {
            "example": {
                "document": "# Title\n\n## Section 1\n\nContent here...",
                "parse_elements": ["headings", "sections"]
            }
        }


class V2DocumentExtractRequest(V2BaseRequest):
    """Extract specific data from documents"""
    document: str = Field(..., description="Document content")
    extract_fields: List[str] = Field(..., description="Fields to extract (e.g., invoice_number, date, total)")

    class Config:
        json_schema_extra = {
            "example": {
                "document": "Invoice #12345\nDate: 2025-10-30\nTotal: €1,250.00",
                "extract_fields": ["invoice_number", "date", "total_amount"]
            }
        }


class V2DocumentStructureRequest(V2BaseRequest):
    """Convert unstructured documents to structured format"""
    document: str = Field(..., description="Unstructured document content")
    target_format: Optional[str] = Field("json", description="Target format (json, markdown, html)")

    class Config:
        json_schema_extra = {
            "example": {
                "document": "Meeting notes: discussed budget, timeline, and next steps...",
                "target_format": "json"
            }
        }


class V2DocumentClassifyRequest(V2BaseRequest):
    """Classify document type/category"""
    document: str = Field(..., description="Document content")
    possible_types: Optional[List[str]] = Field(None, description="Possible document types")

    class Config:
        json_schema_extra = {
            "example": {
                "document": "Invoice #12345...",
                "possible_types": ["invoice", "receipt", "purchase_order", "contract"]
            }
        }


class V2DocumentCompareRequest(V2BaseRequest):
    """Compare multiple documents"""
    documents: List[str] = Field(..., min_items=2, max_items=5, description="Documents to compare")
    comparison_type: Optional[str] = Field("differences", description="differences, similarities, or summary")

    class Config:
        json_schema_extra = {
            "example": {
                "documents": ["Contract v1...", "Contract v2..."],
                "comparison_type": "differences"
            }
        }


class V2DocumentGenerateRequest(V2BaseRequest):
    """Generate complete documents"""
    document_type: str = Field(..., description="Type of document (report, contract, whitepaper, etc.)")
    specifications: Dict[str, Any] = Field(..., description="Document specifications and requirements")

    class Config:
        json_schema_extra = {
            "example": {
                "document_type": "technical_report",
                "specifications": {
                    "title": "Q4 2025 System Performance Analysis",
                    "sections": ["Executive Summary", "Methodology", "Results", "Recommendations"],
                    "tone": "professional",
                    "length": "10-15 pages"
                }
            }
        }


# ============================================================================
# V2 Video Operations Schemas
# ============================================================================

class V2VideoGenerateRequest(V2BaseRequest):
    """Generate video from text or images"""
    prompt: str = Field(..., min_length=10, max_length=5000, description="Video generation prompt")
    prompt_image: Optional[str] = Field(None, description="URL of image for image-to-video generation (required for RunwayML)")
    duration: Optional[int] = Field(5, ge=1, le=30, description="Video duration in seconds")
    aspect_ratio: Optional[str] = Field("16:9", description="16:9, 9:16, 1:1")
    include_audio: Optional[bool] = Field(True, description="Generate synchronized audio")

    class Config:
        json_schema_extra = {
            "example": {
                "prompt": "The bunny hops across the meadow",
                "prompt_image": "https://example.com/bunny.jpg",
                "duration": 5,
                "aspect_ratio": "16:9",
                "include_audio": False
            }
        }


class V2VideoRemixRequest(V2BaseRequest):
    """Remix/edit existing video"""
    video_url: str = Field(..., description="URL of source video")
    instructions: str = Field(..., description="Editing instructions")

    class Config:
        json_schema_extra = {
            "example": {
                "video_url": "https://example.com/video.mp4",
                "instructions": "Add dramatic lighting and slow motion effect"
            }
        }


class V2VideoExtendRequest(V2BaseRequest):
    """Extend video duration"""
    video_url: str = Field(..., description="URL of source video")
    extend_duration: int = Field(..., ge=1, le=30, description="Additional seconds to add")

    class Config:
        json_schema_extra = {
            "example": {
                "video_url": "https://example.com/video.mp4",
                "extend_duration": 5
            }
        }


class V2VideoInterpolateRequest(V2BaseRequest):
    """Create smooth transitions between video frames"""
    video_url: str = Field(..., description="URL of source video")
    target_fps: Optional[int] = Field(60, ge=24, le=120, description="Target frames per second")

    class Config:
        json_schema_extra = {
            "example": {
                "video_url": "https://example.com/video.mp4",
                "target_fps": 60
            }
        }


class V2VideoDescribeRequest(V2BaseRequest):
    """Generate description of video contents"""
    video_url: str = Field(..., description="URL of video to describe")
    detail_level: Optional[str] = Field("medium", description="low, medium, high")

    class Config:
        json_schema_extra = {
            "example": {
                "video_url": "https://example.com/video.mp4",
                "detail_level": "high"
            }
        }


# ============================================================================
# V2 Audio Operations Schemas
# ============================================================================

class V2AudioTranscribeRequest(V2BaseRequest):
    """
    Transcribe audio to text with audio intelligence features

    Supports:
    - Multi-model transcription (best/nano tiers)
    - Speaker diarization (who said what)
    - Sentiment analysis per sentence
    - Entity detection (names, dates, organizations)
    - Auto-summarization with chapters
    - Topic classification (600+ IAB categories)
    - Content moderation
    - PII redaction for privacy
    - Custom vocabulary boosting
    """
    audio_url: str = Field(..., description="Public URL to audio file (REQUIRED)")
    language_code: Optional[str] = Field(None, description="Language hint (e.g., 'en', 'es', 'fr') for better accuracy")

    # Speaker diarization
    speaker_labels: Optional[bool] = Field(False, description="Enable speaker diarization (identify who said what)")
    speakers_expected: Optional[int] = Field(None, ge=1, le=20, description="Expected number of speakers (helps accuracy)")

    # Audio intelligence features
    sentiment_analysis: Optional[bool] = Field(False, description="Analyze sentiment per sentence (positive/negative/neutral)")
    entity_detection: Optional[bool] = Field(False, description="Extract named entities (people, dates, organizations)")
    auto_chapters: Optional[bool] = Field(False, description="Generate chapters with summaries (topic segmentation)")
    summarization: Optional[bool] = Field(False, description="Generate AI-powered summary of the transcript")
    summarization_type: Optional[str] = Field("bullets", description="Summary format: 'bullets', 'paragraph', or 'headline'")

    # Topic classification and content safety
    iab_categories: Optional[bool] = Field(False, description="Classify content into 600+ IAB topic categories")
    content_safety: Optional[bool] = Field(False, description="Detect harmful content (profanity, violence, hate speech)")

    # Content filtering and redaction
    filter_profanity: Optional[bool] = Field(False, description="Replace profanity with asterisks")
    redact_pii: Optional[bool] = Field(False, description="Redact personally identifiable information (SSN, credit cards, etc.)")

    # Custom vocabulary
    word_boost: Optional[List[str]] = Field(None, description="Custom words/phrases to boost recognition accuracy")
    boost_param: Optional[str] = Field("default", description="Boost level: 'low', 'default', or 'high'")

    # Deepgram-specific features
    detect_language: Optional[bool] = Field(False, description="Auto-detect language (Deepgram)")
    smart_format: Optional[bool] = Field(True, description="Smart formatting: punctuation, capitalization, paragraphing (Deepgram)")
    punctuate: Optional[bool] = Field(True, description="Add punctuation (Deepgram)")
    paragraphs: Optional[bool] = Field(False, description="Segment into paragraphs (Deepgram)")
    numerals: Optional[bool] = Field(False, description="Convert written numbers to digits (Deepgram)")
    filler_words: Optional[bool] = Field(False, description="Include filler words like 'uh', 'um' (Deepgram)")
    utterances: Optional[bool] = Field(False, description="Return utterance-level results with speakers (Deepgram)")
    topics: Optional[bool] = Field(False, description="Detect topics (Deepgram)")
    custom_topics: Optional[List[str]] = Field(None, description="Custom topics to detect (Deepgram)")
    intents: Optional[bool] = Field(False, description="Detect user intents (Deepgram)")
    keywords: Optional[List[str]] = Field(None, description="Keywords to boost (up to 100, Deepgram)")
    keyword_boost: Optional[float] = Field(2.0, ge=1.0, le=5.0, description="Keyword boost value (1.0-5.0, Deepgram)")
    search: Optional[List[str]] = Field(None, description="Terms to search for in transcript (Deepgram)")
    replace: Optional[Dict[str, str]] = Field(None, description="Find and replace terms (Deepgram)")
    multichannel: Optional[bool] = Field(False, description="Multi-channel audio processing (Deepgram)")

    class Config:
        json_schema_extra = {
            "example": {
                "audio_url": "https://example.com/meeting.mp3",
                "model": "best",
                "language_code": "en",
                "speaker_labels": True,
                "speakers_expected": 3,
                "sentiment_analysis": True,
                "entity_detection": True,
                "auto_chapters": True,
                "summarization": True,
                "summarization_type": "bullets",
                "provider": "assemblyai"
            }
        }


class V2AudioTranscribeResponse(V2BaseResponse):
    """Response for audio transcription with audio intelligence"""
    text: str = Field(..., description="Full transcript text")
    audio_duration: float = Field(..., description="Audio duration in seconds")
    confidence: Optional[float] = Field(None, description="Overall transcription confidence (0-1)")
    language_code: Optional[str] = Field(None, description="Detected language code")

    # Speaker diarization results
    utterances: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Speaker-labeled utterances: [{speaker, text, start, end, confidence}]"
    )

    # Audio intelligence results
    chapters: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Auto-generated chapters: [{headline, summary, gist, start, end}]"
    )
    entities: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Detected entities: [{entity_type, text, start, end}]"
    )
    sentiment_analysis_results: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Sentiment per sentence: [{text, sentiment, confidence, start, end}]"
    )
    iab_categories_result: Optional[Dict[str, Any]] = Field(
        None,
        description="Topic classification results with relevance scores"
    )
    content_safety_labels: Optional[Dict[str, Any]] = Field(
        None,
        description="Content moderation results with severity levels"
    )
    summary: Optional[str] = Field(None, description="AI-generated summary")

    # Word-level timestamps
    words: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="Word-level timestamps: [{text, start, end, confidence}] (first 100 words)"
    )


class V2AudioSynthesizeRequest(V2BaseRequest):
    """Generate speech from text (TTS)"""
    text: str = Field(..., min_length=1, max_length=10000)
    voice: Optional[str] = Field("default", description="Voice identifier (e.g., 'professional_female') or voice ID")
    voice_id: Optional[str] = Field(None, description="Direct ElevenLabs voice ID (overrides 'voice' parameter)")
    language: Optional[str] = Field("en", description="Target language")
    speed: Optional[float] = Field(1.0, ge=0.5, le=2.0, description="Playback speed multiplier")
    output_format: Optional[str] = Field("mp3_44100_128", description="Audio format (e.g., mp3_44100_128, pcm_44100)")

    # ElevenLabs voice settings (fine-grained control)
    stability: Optional[float] = Field(None, ge=0.0, le=1.0, description="Voice stability (0=expressive, 1=stable)")
    similarity_boost: Optional[float] = Field(None, ge=0.0, le=1.0, description="Voice similarity (0-1)")
    style: Optional[float] = Field(None, ge=0.0, le=1.0, description="Speaking style exaggeration (0-1)")
    use_speaker_boost: Optional[bool] = Field(None, description="Enhance clarity for specific speakers")

    class Config:
        json_schema_extra = {
            "example": {
                "text": "Welcome to our service. How can I help you today?",
                "voice": "professional_female",
                "model": "eleven_flash_v2_5",
                "language": "en",
                "stability": 0.5,
                "similarity_boost": 0.75
            }
        }


class V2AudioSeparateRequest(V2BaseRequest):
    """Separate audio tracks/sources"""
    audio_url: str = Field(..., description="URL of audio file")
    separation_type: str = Field(..., description="vocals, instruments, speech, noise")

    class Config:
        json_schema_extra = {
            "example": {
                "audio_url": "https://example.com/music.mp3",
                "separation_type": "vocals"
            }
        }


class V2AudioEnhanceRequest(V2BaseRequest):
    """Enhance audio quality"""
    audio_url: str = Field(..., description="URL of audio file")
    enhancement_types: List[str] = Field(default=["denoise", "normalize"], description="Types of enhancement")

    class Config:
        json_schema_extra = {
            "example": {
                "audio_url": "https://example.com/recording.mp3",
                "enhancement_types": ["denoise", "normalize", "enhance_clarity"]
            }
        }


# ============================================================================
# V2 Moderation Schemas
# ============================================================================

class V2ModerationRequest(V2BaseRequest):
    """Check content for safety/policy violations"""
    content: str = Field(..., description="Content to moderate")
    content_type: Optional[str] = Field("text", description="text, image_url, video_url")

    class Config:
        json_schema_extra = {
            "example": {
                "content": "Some text content to check",
                "content_type": "text"
            }
        }


class V2DetectionRequest(V2BaseRequest):
    """Detect specific content types"""
    content: str = Field(..., description="Content to analyze")
    detection_types: List[str] = Field(..., description="PII, hate_speech, violence, etc.")

    class Config:
        json_schema_extra = {
            "example": {
                "content": "My email is john@example.com and my phone is 555-1234",
                "detection_types": ["PII", "contact_info"]
            }
        }


class V2PerspectiveAnalyzeRequest(V2BaseRequest):
    """
    Analyze text for toxicity and harmful content using Google Perspective API

    Attributes analyzed:
    - TOXICITY: Overall toxicity likelihood
    - SEVERE_TOXICITY: Very hateful, aggressive content
    - IDENTITY_ATTACK: Negative comments about identity/ethnicity
    - INSULT: Insulting or inflammatory language
    - PROFANITY: Swear words and obscene language
    - THREAT: Threats of violence or harm
    """
    text: str = Field(..., min_length=1, max_length=20000, description="Text to analyze for toxicity")
    requested_attributes: Optional[List[str]] = Field(
        None,
        description="Attributes to analyze: TOXICITY, SEVERE_TOXICITY, IDENTITY_ATTACK, INSULT, PROFANITY, THREAT"
    )
    languages: Optional[List[str]] = Field(
        None,
        description="Language hints (e.g., ['en', 'es']). Auto-detects if not specified."
    )
    do_not_store: bool = Field(
        True,
        description="Don't store comment for future research (privacy mode)"
    )
    span_annotations: bool = Field(
        False,
        description="Return per-sentence toxicity scores"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "text": "This is a sample comment to analyze for toxicity.",
                "requested_attributes": ["TOXICITY", "SEVERE_TOXICITY", "PROFANITY"],
                "languages": ["en"],
                "do_not_store": True,
                "span_annotations": False,
                "provider": "perspective"
            }
        }


class V2PerspectiveAnalyzeResponse(V2BaseResponse):
    """Response for Perspective API toxicity analysis"""
    attribute_scores: Dict[str, Dict[str, Any]] = Field(
        ...,
        description="Scores per attribute: {TOXICITY: {summary_score: 0.85, span_scores: [...]}, ...}"
    )
    detected_languages: Optional[List[str]] = Field(
        None,
        description="Detected language codes"
    )
    is_toxic: Optional[bool] = Field(
        None,
        description="Overall toxicity flag (score >= 0.5)"
    )
    toxicity_level: Optional[str] = Field(
        None,
        description="Severity level: low, medium, high, very_high"
    )
    toxicity_score: Optional[float] = Field(
        None,
        description="Overall TOXICITY score (0-1)"
    )


# ============================================================================
# V2 Embeddings Schema
# ============================================================================

class V2EmbeddingsRequest(V2BaseRequest):
    """Generate vector embeddings"""
    texts: List[str] = Field(..., min_items=1, max_items=100, description="Texts to embed")
    embedding_model: Optional[str] = Field(None, description="Specific embedding model")

    class Config:
        json_schema_extra = {
            "example": {
                "texts": [
                    "What is artificial intelligence?",
                    "How does machine learning work?"
                ],
                "embedding_model": "text-embedding-3-small"
            }
        }


class V2EmbeddingsResponse(V2BaseResponse):
    """Response for embeddings generation"""
    embeddings: List[List[float]] = Field(..., description="Generated embedding vectors")
    dimensions: int = Field(..., description="Embedding dimensions")


# ============================================================================
# V2 Data Operations Schemas (VoyageAI Embeddings & Reranking)
# ============================================================================

class V2DataEmbedRequest(V2BaseRequest):
    """
    Generate semantic embeddings for text(s)

    Embeddings convert text into numerical vectors for semantic search, RAG,
    clustering, and similarity calculations.

    Supports:
    - Single text or batch processing (up to 1000 texts)
    - Asymmetric embeddings (document vs query optimization)
    - Matryoshka embeddings (flexible dimensions)
    - Domain-specific models (code, finance, law)
    """
    texts: Union[str, List[str]] = Field(..., description="Single text or list of texts to embed")
    input_type: Optional[str] = Field(
        None,
        description="'document' for content to search, 'query' for search queries (improves retrieval)"
    )
    output_dimension: Optional[int] = Field(
        None,
        description="Embedding dimensions: 256, 512, 1024, or 2048 (default: model-specific)"
    )
    truncation: Optional[bool] = Field(
        True,
        description="Truncate over-length inputs (default: True)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "texts": [
                    "Python is a high-level programming language",
                    "FastAPI is a modern web framework for Python"
                ],
                "input_type": "document",
                "output_dimension": 1024,
                "model": "voyage-3.5-lite",
                "provider": "voyageai"
            }
        }


class V2DataEmbedResponse(V2BaseResponse):
    """Response for embedding generation"""
    embeddings: List[List[float]] = Field(..., description="List of embedding vectors (one per input text)")
    dimensions: int = Field(..., description="Embedding vector dimensions")
    num_embeddings: int = Field(..., description="Number of embeddings generated")


class V2DataRerankRequest(V2BaseRequest):
    """
    Rerank documents by relevance to a query

    Reranking is a second-stage refinement for search results:
    1. First stage: Fast embedding-based search (retrieve ~100 candidates)
    2. Second stage: Reranker scores each candidate (refine to top 10)

    Provides more accurate relevance scores than embeddings alone.
    """
    query: str = Field(..., min_length=1, max_length=8000, description="Search query")
    documents: List[str] = Field(
        ...,
        min_items=1,
        max_items=1000,
        description="List of documents to rank by relevance"
    )
    top_k: Optional[int] = Field(
        None,
        ge=1,
        description="Return only top K most relevant documents (default: all)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "query": "How to deploy FastAPI with Docker?",
                "documents": [
                    "FastAPI deployment guide with Docker and Kubernetes",
                    "Introduction to Python web frameworks",
                    "FastAPI tutorial for beginners",
                    "Docker best practices for production"
                ],
                "top_k": 2,
                "model": "rerank-2.5-lite",
                "provider": "voyageai"
            }
        }


class V2DataRerankResponse(V2BaseResponse):
    """Response for document reranking"""
    results: List[Dict[str, Any]] = Field(
        ...,
        description="Ranked documents: [{index, text, score}, ...]. Score 0-1, higher=more relevant"
    )
    num_results: int = Field(..., description="Number of results returned")
