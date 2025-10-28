"""
SQLAlchemy ORM Models for LLM Microservice
Maps to TimescaleDB schema tables
"""

from sqlalchemy import Column, String, Integer, Boolean, Text, DECIMAL, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy import TIMESTAMP
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import uuid

from src.config.database import Base


# ============================================================================
# APIClient Model
# ============================================================================

class APIClient(Base):
    """API clients registered to use the LLM service"""

    __tablename__ = "api_clients"

    client_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    client_name = Column(String(255), unique=True, nullable=False, index=True)
    api_key = Column(Text, unique=True, nullable=False, index=True)
    organization = Column(String(255))
    contact_email = Column(String(255))
    is_active = Column(Boolean, default=True, index=True)
    rate_limit = Column(Integer, default=100)  # requests per minute
    monthly_budget_usd = Column(DECIMAL(10, 2))
    created_at = Column(TIMESTAMP(timezone=True), default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), default=func.now(), onupdate=func.now())

    # Relationships
    prompt_templates = relationship("PromptTemplate", back_populates="owner", foreign_keys="PromptTemplate.owner_client_id")
    generation_logs = relationship("LLMGenerationLog", back_populates="client")

    def __repr__(self):
        return f"<APIClient(client_name='{self.client_name}', organization='{self.organization}')>"


# ============================================================================
# PromptTemplate Model
# ============================================================================

class PromptTemplate(Base):
    """Reusable prompt templates with variable substitution"""

    __tablename__ = "prompt_templates"

    template_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_name = Column(String(255), nullable=False)
    template_type = Column(String(50), nullable=False, index=True)  # whitepaper, linkedin_post, etc.
    description = Column(Text)
    system_prompt = Column(Text, nullable=False)
    user_prompt_template = Column(Text, nullable=False)
    variables = Column(JSONB)  # {"topic": "string", "audience": "string"}
    output_config = Column(JSONB)  # {"format": "markdown", "max_length": 5000}
    is_public = Column(Boolean, default=False, index=True)
    owner_client_id = Column(UUID(as_uuid=True), ForeignKey("api_clients.client_id", ondelete="SET NULL"), nullable=True)
    usage_count = Column(Integer, default=0)
    success_rate = Column(DECIMAL(5, 2))
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(TIMESTAMP(timezone=True), default=func.now())
    updated_at = Column(TIMESTAMP(timezone=True), default=func.now(), onupdate=func.now())

    # Relationships
    owner = relationship("APIClient", back_populates="prompt_templates", foreign_keys=[owner_client_id])
    versions = relationship("PromptVersion", back_populates="template", cascade="all, delete-orphan")
    generation_logs = relationship("LLMGenerationLog", back_populates="template")

    # Indexes
    __table_args__ = (
        Index('idx_templates_type', template_type),
        Index('idx_templates_owner', owner_client_id),
    )

    def __repr__(self):
        return f"<PromptTemplate(name='{self.template_name}', type='{self.template_type}')>"


# ============================================================================
# PromptVersion Model
# ============================================================================

class PromptVersion(Base):
    """Version history for prompt templates (A/B testing)"""

    __tablename__ = "prompt_versions"

    version_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    template_id = Column(UUID(as_uuid=True), ForeignKey("prompt_templates.template_id", ondelete="CASCADE"), nullable=False)
    version_number = Column(Integer, nullable=False)
    changes_description = Column(Text)
    prompt_content = Column(JSONB, nullable=False)  # Snapshot of prompts
    performance_score = Column(DECIMAL(5, 2))
    is_default = Column(Boolean, default=False)
    status = Column(String(50), default="draft")  # draft, testing, production, archived
    created_at = Column(TIMESTAMP(timezone=True), default=func.now())
    created_by = Column(UUID(as_uuid=True), ForeignKey("api_clients.client_id", ondelete="SET NULL"))

    # Relationships
    template = relationship("PromptTemplate", back_populates="versions")

    # Unique constraint
    __table_args__ = (
        Index('idx_versions_template', template_id, version_number.desc()),
        Index('idx_versions_default', template_id, is_default),
        {'extend_existing': True}
    )

    def __repr__(self):
        return f"<PromptVersion(template_id='{self.template_id}', version={self.version_number})>"


# ============================================================================
# LLMGenerationLog Model (Time-Series Data)
# ============================================================================

class LLMGenerationLog(Base):
    """Time-series log of all LLM API calls with billing data"""

    __tablename__ = "llm_generation_log"

    log_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(TIMESTAMP(timezone=True), primary_key=True, default=func.now(), nullable=False)  # Part of composite PK for hypertable
    client_id = Column(UUID(as_uuid=True), ForeignKey("api_clients.client_id"), index=True)
    template_id = Column(UUID(as_uuid=True), ForeignKey("prompt_templates.template_id"), nullable=True)
    endpoint = Column(String(100), nullable=False, index=True)  # /generate-content, /translate
    provider = Column(String(50), nullable=False, index=True)  # claude, openai, groq
    model = Column(String(255), nullable=False)
    input_tokens = Column(Integer)
    output_tokens = Column(Integer)
    # total_tokens is a generated column in database, not mapped here
    input_cost_usd = Column(DECIMAL(10, 6))
    output_cost_usd = Column(DECIMAL(10, 6))
    # total_cost_usd is a generated column in database
    generation_time_ms = Column(Integer)
    success = Column(Boolean, nullable=False, index=True)
    error_message = Column(Text)
    error_type = Column(String(100))  # rate_limit, invalid_request, timeout
    request_metadata = Column(JSONB)  # Prompt details, languages, parameters
    response_metadata = Column(JSONB)  # Response quality, flags

    # Relationships
    client = relationship("APIClient", back_populates="generation_logs")
    template = relationship("PromptTemplate", back_populates="generation_logs")

    # Indexes (defined in schema, but listed here for reference)
    __table_args__ = (
        Index('idx_log_client_time', client_id, created_at.desc()),
        Index('idx_log_provider_time', provider, created_at.desc()),
        Index('idx_log_endpoint_time', endpoint, created_at.desc()),
        Index('idx_log_success', success, created_at.desc()),
    )

    def __repr__(self):
        return f"<LLMGenerationLog(provider='{self.provider}', model='{self.model}', success={self.success})>"

    @property
    def total_tokens(self) -> int:
        """Calculate total tokens (generated column in DB, computed here for ORM)"""
        return (self.input_tokens or 0) + (self.output_tokens or 0)

    @property
    def total_cost_usd(self) -> float:
        """Calculate total cost (generated column in DB, computed here for ORM)"""
        return float((self.input_cost_usd or 0) + (self.output_cost_usd or 0))
