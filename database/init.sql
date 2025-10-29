-- ============================================================================
-- LLMHub Database Schema (TimescaleDB)
-- Application-Agnostic LLM Service with Billing Tracking
-- ============================================================================

-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ============================================================================
-- TABLE: api_clients
-- Track all applications/clients using the LLM service
-- ============================================================================

CREATE TABLE api_clients (
  client_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  client_name VARCHAR(255) UNIQUE NOT NULL,  -- 'recloud-marketing', 'acme-corp', etc.
  api_key TEXT UNIQUE NOT NULL,
  organization VARCHAR(255),
  contact_email VARCHAR(255),
  is_active BOOLEAN DEFAULT true,
  rate_limit INTEGER DEFAULT 100,  -- requests per minute
  monthly_budget_usd DECIMAL(10,2),  -- Optional spending limit
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_api_clients_active ON api_clients(is_active);
CREATE INDEX idx_api_clients_api_key ON api_clients(api_key);

COMMENT ON TABLE api_clients IS 'API clients registered to use the LLM service';
COMMENT ON COLUMN api_clients.rate_limit IS 'Maximum requests per minute for this client';
COMMENT ON COLUMN api_clients.monthly_budget_usd IS 'Optional monthly spending limit in USD';

-- ============================================================================
-- TABLE: llm_providers
-- LLM Provider configurations (Claude, OpenAI, Groq, etc.)
-- ============================================================================

CREATE TABLE llm_providers (
  provider_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  provider_key VARCHAR(50) UNIQUE NOT NULL,  -- 'claude', 'openai', 'groq'
  display_name VARCHAR(255) NOT NULL,  -- 'Anthropic Claude', 'OpenAI', 'Groq'
  description TEXT,
  api_key_env_var VARCHAR(100),  -- 'ANTHROPIC_API_KEY', 'OPENAI_API_KEY', 'GROQ_API_KEY'
  logo_url TEXT,
  website_url TEXT,
  is_active BOOLEAN DEFAULT true,
  sort_order INTEGER DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_providers_active ON llm_providers(is_active);
CREATE INDEX idx_providers_key ON llm_providers(provider_key);

COMMENT ON TABLE llm_providers IS 'LLM provider configurations';
COMMENT ON COLUMN llm_providers.provider_key IS 'Internal key used in code (lowercase, no spaces)';
COMMENT ON COLUMN llm_providers.api_key_env_var IS 'Environment variable name for API key';

-- ============================================================================
-- TABLE: llm_models
-- Available LLM models with cost and pricing configuration
-- ============================================================================

CREATE TABLE llm_models (
  model_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  provider_id UUID REFERENCES llm_providers(provider_id) ON DELETE CASCADE,
  model_key VARCHAR(255) UNIQUE NOT NULL,  -- 'claude-3-5-sonnet-20241022', 'gpt-4-turbo-preview'
  display_name VARCHAR(255) NOT NULL,  -- 'Claude 3.5 Sonnet', 'GPT-4 Turbo'
  description TEXT,
  context_window VARCHAR(50),  -- '200K', '128K', '32K'
  cost_per_million_input DECIMAL(10,6) NOT NULL,  -- Cost charged by provider (per 1M input tokens)
  cost_per_million_output DECIMAL(10,6) NOT NULL,  -- Cost charged by provider (per 1M output tokens)
  price_per_million_input DECIMAL(10,6) NOT NULL,  -- Price we charge to clients (per 1M input tokens)
  price_per_million_output DECIMAL(10,6) NOT NULL,  -- Price we charge to clients (per 1M output tokens)
  is_enabled BOOLEAN DEFAULT true,  -- Can be used for new requests
  is_active BOOLEAN DEFAULT true,  -- Soft delete flag
  sort_order INTEGER DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_models_provider ON llm_models(provider_id);
CREATE INDEX idx_models_key ON llm_models(model_key);
CREATE INDEX idx_models_enabled ON llm_models(is_enabled) WHERE is_enabled = true;
CREATE INDEX idx_models_active ON llm_models(is_active) WHERE is_active = true;

COMMENT ON TABLE llm_models IS 'LLM models with cost (from provider) and price (to clients) configuration';
COMMENT ON COLUMN llm_models.cost_per_million_input IS 'Provider cost per 1M input tokens in USD';
COMMENT ON COLUMN llm_models.cost_per_million_output IS 'Provider cost per 1M output tokens in USD';
COMMENT ON COLUMN llm_models.price_per_million_input IS 'Our price to clients per 1M input tokens in USD';
COMMENT ON COLUMN llm_models.price_per_million_output IS 'Our price to clients per 1M output tokens in USD';
COMMENT ON COLUMN llm_models.is_enabled IS 'Whether this model can be used for new requests';

-- ============================================================================
-- TABLE: prompt_templates
-- Reusable prompt templates shared across all clients
-- ============================================================================

CREATE TABLE prompt_templates (
  template_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  template_name VARCHAR(255) NOT NULL,
  template_type VARCHAR(50) NOT NULL,  -- 'whitepaper', 'linkedin_post', '1pager', 'email', 'translation'
  description TEXT,
  system_prompt TEXT NOT NULL,
  user_prompt_template TEXT NOT NULL,
  variables JSONB,  -- {"topic": "string", "audience": "string"}
  output_config JSONB,  -- {"format": "markdown", "max_length": 5000}
  is_public BOOLEAN DEFAULT false,  -- Public templates available to all clients
  owner_client_id UUID REFERENCES api_clients(client_id) ON DELETE SET NULL,  -- NULL = system template
  usage_count INTEGER DEFAULT 0,
  success_rate DECIMAL(5,2),
  is_active BOOLEAN DEFAULT true,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_templates_type ON prompt_templates(template_type);
CREATE INDEX idx_templates_owner ON prompt_templates(owner_client_id);
CREATE INDEX idx_templates_public ON prompt_templates(is_public) WHERE is_public = true;
CREATE INDEX idx_templates_active ON prompt_templates(is_active) WHERE is_active = true;

COMMENT ON TABLE prompt_templates IS 'Reusable prompt templates with variable substitution';
COMMENT ON COLUMN prompt_templates.is_public IS 'Public templates are available to all API clients';
COMMENT ON COLUMN prompt_templates.owner_client_id IS 'NULL indicates system-provided template';

-- ============================================================================
-- TABLE: prompt_versions
-- Version history for prompt templates (A/B testing, optimization)
-- ============================================================================

CREATE TABLE prompt_versions (
  version_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  template_id UUID REFERENCES prompt_templates(template_id) ON DELETE CASCADE,
  version_number INTEGER NOT NULL,
  changes_description TEXT,
  prompt_content JSONB NOT NULL,  -- Snapshot of system_prompt + user_prompt_template
  performance_score DECIMAL(5,2),
  is_default BOOLEAN DEFAULT false,
  status VARCHAR(50) DEFAULT 'draft',  -- 'draft', 'testing', 'production', 'archived'
  created_at TIMESTAMPTZ DEFAULT NOW(),
  created_by UUID REFERENCES api_clients(client_id) ON DELETE SET NULL,
  UNIQUE(template_id, version_number)
);

CREATE INDEX idx_versions_template ON prompt_versions(template_id, version_number DESC);
CREATE INDEX idx_versions_default ON prompt_versions(template_id, is_default) WHERE is_default = true;

COMMENT ON TABLE prompt_versions IS 'Version history for prompt templates for A/B testing';

-- ============================================================================
-- TABLE: llm_generation_log (TIME-SERIES DATA)
-- Audit trail and billing data for all LLM API calls
-- ============================================================================

CREATE TABLE llm_generation_log (
  log_id UUID DEFAULT gen_random_uuid(),
  created_at TIMESTAMPTZ DEFAULT NOW() NOT NULL,
  client_id UUID REFERENCES api_clients(client_id),
  template_id UUID REFERENCES prompt_templates(template_id),
  endpoint VARCHAR(100) NOT NULL,  -- '/generate-content', '/translate', '/improve-content', '/generate-image'
  provider VARCHAR(50) NOT NULL,   -- 'claude', 'openai', 'groq'
  model VARCHAR(255) NOT NULL,     -- 'claude-3-5-sonnet-20241022', 'gpt-4', etc.
  input_tokens INTEGER,
  output_tokens INTEGER,
  total_tokens INTEGER GENERATED ALWAYS AS (COALESCE(input_tokens, 0) + COALESCE(output_tokens, 0)) STORED,
  input_cost_usd DECIMAL(10,6),
  output_cost_usd DECIMAL(10,6),
  total_cost_usd DECIMAL(10,6) GENERATED ALWAYS AS (COALESCE(input_cost_usd, 0) + COALESCE(output_cost_usd, 0)) STORED,
  generation_time_ms INTEGER,
  success BOOLEAN NOT NULL,
  error_message TEXT,
  error_type VARCHAR(100),  -- 'rate_limit', 'invalid_request', 'timeout', 'provider_error'
  request_metadata JSONB,  -- Store prompt details, languages requested, etc.
  response_metadata JSONB,  -- Store response details, quality scores, etc.
  PRIMARY KEY (log_id, created_at)
);

-- Convert to TimescaleDB hypertable for time-series optimization
SELECT create_hypertable('llm_generation_log', 'created_at');

-- Indexes for fast queries
CREATE INDEX idx_log_client_time ON llm_generation_log (client_id, created_at DESC);
CREATE INDEX idx_log_provider_time ON llm_generation_log (provider, created_at DESC);
CREATE INDEX idx_log_endpoint_time ON llm_generation_log (endpoint, created_at DESC);
CREATE INDEX idx_log_success ON llm_generation_log (success, created_at DESC);
CREATE INDEX idx_log_template ON llm_generation_log (template_id, created_at DESC) WHERE template_id IS NOT NULL;

COMMENT ON TABLE llm_generation_log IS 'Time-series log of all LLM API calls with billing data';
COMMENT ON COLUMN llm_generation_log.request_metadata IS 'JSONB: prompt, languages, parameters used';
COMMENT ON COLUMN llm_generation_log.response_metadata IS 'JSONB: response quality, flags, metadata';

-- ============================================================================
-- CONTINUOUS AGGREGATION: llm_hourly_costs
-- Real-time hourly cost aggregation
-- ============================================================================

CREATE MATERIALIZED VIEW llm_hourly_costs
WITH (timescaledb.continuous) AS
SELECT
  time_bucket('1 hour', created_at) AS hour,
  client_id,
  provider,
  endpoint,
  COUNT(*) as call_count,
  SUM(total_tokens) as total_tokens,
  SUM(total_cost_usd) as total_cost,
  AVG(generation_time_ms) as avg_generation_time_ms,
  SUM(CASE WHEN success THEN 1 ELSE 0 END)::FLOAT / NULLIF(COUNT(*), 0) as success_rate
FROM llm_generation_log
GROUP BY hour, client_id, provider, endpoint;

-- Note: Cannot add COMMENT to TimescaleDB continuous aggregates (not regular materialized views)

-- Add refresh policy (refresh every hour)
SELECT add_continuous_aggregate_policy('llm_hourly_costs',
  start_offset => INTERVAL '2 hours',
  end_offset => INTERVAL '1 hour',
  schedule_interval => INTERVAL '1 hour');

-- ============================================================================
-- CONTINUOUS AGGREGATION: llm_daily_costs
-- Daily cost aggregation for billing reports
-- ============================================================================

CREATE MATERIALIZED VIEW llm_daily_costs
WITH (timescaledb.continuous) AS
SELECT
  time_bucket('1 day', created_at) AS day,
  client_id,
  provider,
  endpoint,
  COUNT(*) as call_count,
  SUM(total_tokens) as total_tokens,
  SUM(total_cost_usd) as total_cost,
  AVG(generation_time_ms) as avg_generation_time_ms,
  SUM(CASE WHEN success THEN 1 ELSE 0 END)::FLOAT / NULLIF(COUNT(*), 0) as success_rate,
  COUNT(DISTINCT template_id) as unique_templates_used
FROM llm_generation_log
GROUP BY day, client_id, provider, endpoint;

-- Note: Cannot add COMMENT to TimescaleDB continuous aggregates

-- Add refresh policy (refresh once per day)
SELECT add_continuous_aggregate_policy('llm_daily_costs',
  start_offset => INTERVAL '3 days',
  end_offset => INTERVAL '1 day',
  schedule_interval => INTERVAL '1 day');

-- ============================================================================
-- CONTINUOUS AGGREGATION: llm_monthly_billing
-- Monthly billing summary per client
-- ============================================================================

CREATE MATERIALIZED VIEW llm_monthly_billing
WITH (timescaledb.continuous) AS
SELECT
  time_bucket('1 month', created_at) AS month,
  client_id,
  provider,
  COUNT(*) as total_calls,
  SUM(total_tokens) as total_tokens,
  SUM(total_cost_usd) as total_cost,
  SUM(CASE WHEN success THEN 1 ELSE 0 END)::FLOAT / NULLIF(COUNT(*), 0) as success_rate
FROM llm_generation_log
GROUP BY month, client_id, provider;

-- Note: Cannot add COMMENT to TimescaleDB continuous aggregates

-- Add refresh policy (refresh weekly)
SELECT add_continuous_aggregate_policy('llm_monthly_billing',
  start_offset => INTERVAL '2 months',
  end_offset => INTERVAL '1 day',
  schedule_interval => INTERVAL '1 week');

-- ============================================================================
-- RETENTION POLICY
-- Keep raw data for 90 days, aggregated data forever
-- ============================================================================

SELECT add_retention_policy('llm_generation_log', INTERVAL '90 days');

COMMENT ON EXTENSION timescaledb IS 'Raw LLM logs retained for 90 days; aggregated views kept indefinitely';

-- ============================================================================
-- HELPER VIEWS FOR COMMON QUERIES
-- ============================================================================

-- Current month costs per client
CREATE VIEW v_current_month_costs AS
SELECT
  c.client_name,
  c.organization,
  SUM(m.total_cost) as total_cost_usd,
  SUM(m.total_calls) as total_calls,
  SUM(m.total_tokens) as total_tokens,
  AVG(m.success_rate) as avg_success_rate
FROM llm_monthly_billing m
JOIN api_clients c ON m.client_id = c.client_id
WHERE m.month = time_bucket('1 month', NOW())
GROUP BY c.client_name, c.organization
ORDER BY total_cost_usd DESC;

-- Client budget alerts (clients over 80% of monthly budget)
CREATE VIEW v_budget_alerts AS
SELECT
  c.client_name,
  c.monthly_budget_usd,
  COALESCE(v.total_cost_usd, 0) as current_month_cost,
  ROUND((COALESCE(v.total_cost_usd, 0) / NULLIF(c.monthly_budget_usd, 0) * 100)::numeric, 2) as budget_used_pct
FROM api_clients c
LEFT JOIN v_current_month_costs v ON c.client_name = v.client_name
WHERE c.monthly_budget_usd IS NOT NULL
  AND COALESCE(v.total_cost_usd, 0) > (c.monthly_budget_usd * 0.8)
ORDER BY budget_used_pct DESC;

-- ============================================================================
-- SEED DATA: System Prompt Templates
-- ============================================================================

INSERT INTO prompt_templates (template_name, template_type, description, system_prompt, user_prompt_template, variables, output_config, is_public, owner_client_id) VALUES

-- Whitepaper Template
('Technical Whitepaper Generator (10-15 pages)', 'whitepaper', 'Comprehensive B2B technical whitepapers with compliance focus',
  'You are a senior technical content specialist and B2B marketing writer with expertise in cloud infrastructure, data centers, and compliance standards. Your task is to create authoritative, well-researched whitepapers that educate technical decision-makers while positioning products/services as solutions.

Key writing principles:
- Start with an executive summary (1 page)
- Use clear section headings and logical flow
- Include technical details without being overly complex
- Reference industry standards and compliance frameworks
- Use data and statistics to support claims
- Include diagrams, tables, and visual aids where helpful
- End with actionable recommendations and next steps
- Maintain professional, authoritative tone
- Target audience: CTOs, IT Directors, Infrastructure Managers',

  'Create a comprehensive 10-15 page technical whitepaper about {{topic}}.

Target Audience: {{target_audience}}
Industry Focus: {{industry}}
Key Benefits to Emphasize: {{key_benefits}}
Compliance Requirements: {{compliance_requirements}}

Structure:
1. Executive Summary
2. Industry Challenges
3. Technical Solution Overview
4. Architecture & Implementation
5. Compliance & Security
6. ROI & Business Case
7. Conclusion & Recommendations

Format: Professional markdown with clear headings, bullet points, and tables where appropriate.',

  '{"topic": {"type": "string", "description": "Main whitepaper topic", "required": true}, "target_audience": {"type": "string", "description": "Primary reader persona", "required": true}, "industry": {"type": "string", "description": "Industry vertical (finance, healthcare, government)", "required": false}, "key_benefits": {"type": "string", "description": "Main value propositions to highlight", "required": true}, "compliance_requirements": {"type": "string", "description": "Relevant standards (ISO 27001, GDPR, HIPAA, DORA)", "required": false}}',

  '{"format": "markdown", "min_length": 5000, "max_length": 10000, "include_toc": true}',
  true, NULL),

-- LinkedIn Post Template
('LinkedIn Professional Post', 'linkedin_post', 'Engaging LinkedIn posts with professional tone for B2B audiences',
  'You are a LinkedIn content strategist specializing in B2B professional posts. Create engaging, authentic posts that spark conversation while maintaining professionalism.

Best practices:
- Hook readers in the first line
- Keep paragraphs short (1-2 sentences)
- Use line breaks for readability
- Include a call-to-action or question at the end
- Use emojis sparingly (max 2-3)
- 100-200 words ideal length
- Avoid corporate jargon
- Be conversational but professional',

  'Write a LinkedIn post about {{topic}}.

Tone: {{tone}}
Call-to-action: {{cta}}

Make it engaging, authentic, and conversation-starting.',

  '{"topic": {"type": "string", "description": "Post topic or message", "required": true}, "tone": {"type": "enum", "values": ["professional", "casual", "thought-leadership", "personal-story"], "default": "professional"}, "cta": {"type": "string", "description": "Desired call-to-action", "required": false}}',

  '{"format": "plain_text", "max_length": 300}',
  true, NULL),

-- Business Case 1-Pager Template
('Business Case 1-Pager', '1pager', 'Concise one-page business case documents for decision-makers',
  'You are a business strategy consultant creating concise, data-driven business case documents. Your 1-pagers must communicate value clearly and convince decision-makers quickly.

Structure:
- Problem Statement (2-3 sentences)
- Proposed Solution (3-4 sentences)
- Key Benefits (3-5 bullet points)
- Financial Impact (ROI, cost savings, revenue potential)
- Implementation Overview (timeline, resources)
- Recommendation (clear next step)

Style:
- Use bullet points for scannability
- Include numbers and metrics
- Be specific and actionable
- Avoid fluff and jargon
- Target: Senior executives with limited time',

  'Create a concise 1-page business case for {{solution}}.

Problem Context: {{problem}}
Target Audience: {{audience}}
Expected ROI: {{roi}}
Implementation Timeline: {{timeline}}

Format as a professional business document with clear sections and bullet points.',

  '{"solution": {"type": "string", "description": "Proposed solution or initiative", "required": true}, "problem": {"type": "string", "description": "Business problem being addressed", "required": true}, "audience": {"type": "string", "description": "Decision-maker role", "required": true}, "roi": {"type": "string", "description": "Expected return on investment", "required": false}, "timeline": {"type": "string", "description": "Implementation timeline", "required": false}}',

  '{"format": "markdown", "max_length": 1000}',
  true, NULL),

-- Sales Email Template
('Sales Email - Cold Outreach', 'email', 'Personalized B2B sales emails with high engagement potential',
  'You are a top-performing B2B sales development representative. Write personalized, non-salesy cold outreach emails that get replies.

Email principles:
- Personalized subject line (reference their company/role)
- Open with context (how you found them, mutual connection, recent company news)
- Quickly establish relevance (their pain point)
- Offer value first (insight, resource, idea)
- Keep it short (under 100 words)
- Single, clear call-to-action
- Professional but conversational tone
- No hard selling in first email',

  'Write a cold outreach email to a {{recipient_role}} at {{company}}.

Our Product/Service: {{product}}
Value Proposition: {{value_prop}}
Reason for Outreach: {{reason}}

Subject line and email body. Keep it under 100 words.',

  '{"recipient_role": {"type": "string", "description": "Recipient job title", "required": true}, "company": {"type": "string", "description": "Target company name", "required": true}, "product": {"type": "string", "description": "Product/service being offered", "required": true}, "value_prop": {"type": "string", "description": "Main value proposition", "required": true}, "reason": {"type": "string", "description": "Reason for reaching out now", "required": false}}',

  '{"format": "plain_text", "max_length": 500, "include_subject": true}',
  true, NULL),

-- Translation Template
('Content Translation', 'translation', 'Preserve formatting and tone while translating content between languages',
  'You are a professional translator specializing in technical and marketing content. Maintain the original tone, formatting, and intent while translating accurately.

Translation guidelines:
- Preserve all markdown formatting (headers, lists, links, bold, italic)
- Maintain technical terminology accuracy
- Keep brand names untranslated
- Adapt idioms and cultural references appropriately
- Match the tone of the original (professional, casual, technical)
- For marketing content: prioritize persuasiveness over literal translation
- For technical content: prioritize accuracy and clarity',

  'Translate the following {{content_type}} content from {{source_language}} to {{target_language}}.

Original content:
{{content}}

Preserve all formatting. Maintain the original tone and intent.',

  '{"content": {"type": "string", "description": "Content to translate", "required": true}, "source_language": {"type": "string", "description": "Source language code (en, de, fr, it)", "required": true}, "target_language": {"type": "string", "description": "Target language code", "required": true}, "content_type": {"type": "enum", "values": ["marketing", "technical", "legal", "general"], "default": "general"}}',

  '{"format": "preserve_original"}',
  true, NULL);

-- ============================================================================
-- SEED DATA: LLM Providers
-- ============================================================================

INSERT INTO llm_providers (provider_key, display_name, description, api_key_env_var, sort_order) VALUES
('claude', 'Anthropic Claude', 'Advanced AI assistant with 200K context window and superior reasoning capabilities', 'ANTHROPIC_API_KEY', 1),
('openai', 'OpenAI', 'GPT-4 and DALL-E image generation with wide ecosystem support', 'OPENAI_API_KEY', 2),
('groq', 'Groq', 'Ultra-fast inference with open-source models on custom hardware', 'GROQ_API_KEY', 3);

-- ============================================================================
-- SEED DATA: LLM Models
-- Note: Costs are per 1M tokens (converted from per 1K by multiplying by 1000)
--       Prices include a markup over cost (typically 1.5-2x for margin)
-- ============================================================================

-- Anthropic Claude Models
INSERT INTO llm_models (provider_id, model_key, display_name, description, context_window, cost_per_million_input, cost_per_million_output, price_per_million_input, price_per_million_output, is_enabled, sort_order)
SELECT
  provider_id,
  'claude-3-5-sonnet-20241022',
  'Claude 3.5 Sonnet',
  'Most intelligent model, best for complex tasks requiring deep reasoning',
  '200K',
  3.00,    -- $0.003 per 1K = $3.00 per 1M
  15.00,   -- $0.015 per 1K = $15.00 per 1M
  4.50,    -- 1.5x markup
  22.50,   -- 1.5x markup
  true,
  1
FROM llm_providers WHERE provider_key = 'claude'
UNION ALL
SELECT
  provider_id,
  'claude-3-opus-20240229',
  'Claude 3 Opus',
  'Most powerful model for highly complex tasks requiring maximum intelligence',
  '200K',
  15.00,   -- $0.015 per 1K = $15.00 per 1M
  75.00,   -- $0.075 per 1K = $75.00 per 1M
  22.50,   -- 1.5x markup
  112.50,  -- 1.5x markup
  false,
  2
FROM llm_providers WHERE provider_key = 'claude'
UNION ALL
SELECT
  provider_id,
  'claude-3-haiku-20240307',
  'Claude 3 Haiku',
  'Fastest and most cost-effective model for simple tasks and high-volume processing',
  '200K',
  0.25,    -- $0.00025 per 1K = $0.25 per 1M
  1.25,    -- $0.00125 per 1K = $1.25 per 1M
  0.38,    -- 1.5x markup
  1.88,    -- 1.5x markup
  true,
  3
FROM llm_providers WHERE provider_key = 'claude';

-- OpenAI Models
INSERT INTO llm_models (provider_id, model_key, display_name, description, context_window, cost_per_million_input, cost_per_million_output, price_per_million_input, price_per_million_output, is_enabled, sort_order)
SELECT
  provider_id,
  'gpt-4-turbo-preview',
  'GPT-4 Turbo',
  'Most capable OpenAI model with improved efficiency and 128K context window',
  '128K',
  10.00,   -- $0.01 per 1K = $10.00 per 1M
  30.00,   -- $0.03 per 1K = $30.00 per 1M
  15.00,   -- 1.5x markup
  45.00,   -- 1.5x markup
  true,
  1
FROM llm_providers WHERE provider_key = 'openai'
UNION ALL
SELECT
  provider_id,
  'gpt-4',
  'GPT-4',
  'Original GPT-4 model with excellent reasoning capabilities',
  '8K',
  30.00,   -- $0.03 per 1K = $30.00 per 1M
  60.00,   -- $0.06 per 1K = $60.00 per 1M
  45.00,   -- 1.5x markup
  90.00,   -- 1.5x markup
  false,
  2
FROM llm_providers WHERE provider_key = 'openai'
UNION ALL
SELECT
  provider_id,
  'gpt-3.5-turbo',
  'GPT-3.5 Turbo',
  'Fast and cost-effective model suitable for most tasks',
  '16K',
  1.50,    -- $0.0015 per 1K = $1.50 per 1M
  2.00,    -- $0.002 per 1K = $2.00 per 1M
  2.25,    -- 1.5x markup
  3.00,    -- 1.5x markup
  true,
  3
FROM llm_providers WHERE provider_key = 'openai';

-- Groq Models
INSERT INTO llm_models (provider_id, model_key, display_name, description, context_window, cost_per_million_input, cost_per_million_output, price_per_million_input, price_per_million_output, is_enabled, sort_order)
SELECT
  provider_id,
  'mixtral-8x7b-32768',
  'Mixtral 8x7B',
  'High quality open-source model with extremely fast inference speed',
  '32K',
  0.27,    -- $0.00027 per 1K = $0.27 per 1M
  0.27,    -- $0.00027 per 1K = $0.27 per 1M
  0.54,    -- 2x markup (higher margin on cheap models)
  0.54,    -- 2x markup
  true,
  1
FROM llm_providers WHERE provider_key = 'groq'
UNION ALL
SELECT
  provider_id,
  'llama2-70b-4096',
  'LLaMA 2 70B',
  'Large open-source model with good performance on diverse tasks',
  '4K',
  0.07,    -- $0.00007 per 1K = $0.07 per 1M
  0.07,    -- $0.00007 per 1K = $0.07 per 1M
  0.14,    -- 2x markup
  0.14,    -- 2x markup
  false,
  2
FROM llm_providers WHERE provider_key = 'groq';

-- ============================================================================
-- SEED DATA: Initial API Clients (RE-CLOUD applications)
-- ============================================================================

INSERT INTO api_clients (client_name, api_key, organization, contact_email, rate_limit, monthly_budget_usd) VALUES
('recloud-marketing', 'recloud_marketing_' || encode(gen_random_bytes(16), 'hex'), 'RE-CLOUD GmbH', 'admin@re-cloud.io', 200, 500.00),
('recloud-sales', 'recloud_sales_' || encode(gen_random_bytes(16), 'hex'), 'RE-CLOUD GmbH', 'admin@re-cloud.io', 200, 300.00),
('recloud-email-automation', 'recloud_email_' || encode(gen_random_bytes(16), 'hex'), 'RE-CLOUD GmbH', 'admin@re-cloud.io', 500, 200.00);

-- ============================================================================
-- GRANT PERMISSIONS (if using separate application user)
-- ============================================================================

-- For production: Create separate read-only user for reporting
-- CREATE USER llm_reporting WITH PASSWORD 'reporting_password';
-- GRANT CONNECT ON DATABASE llm_hub TO llm_reporting;
-- GRANT SELECT ON ALL TABLES IN SCHEMA public TO llm_reporting;
-- GRANT SELECT ON llm_hourly_costs, llm_daily_costs, llm_monthly_billing TO llm_reporting;

-- ============================================================================
-- COMPLETION MESSAGE
-- ============================================================================

DO $$
DECLARE
  client_count INTEGER;
  template_count INTEGER;
BEGIN
  SELECT COUNT(*) INTO client_count FROM api_clients;
  SELECT COUNT(*) INTO template_count FROM prompt_templates;

  RAISE NOTICE '✅ LLMHub Database Initialized Successfully';
  RAISE NOTICE '   - TimescaleDB extension enabled';
  RAISE NOTICE '   - Hypertable created: llm_generation_log';
  RAISE NOTICE '   - Continuous aggregations: hourly, daily, monthly';
  RAISE NOTICE '   - Retention policy: 90 days for raw data';
  RAISE NOTICE '   - API clients seeded: %', client_count;
  RAISE NOTICE '   - System templates seeded: %', template_count;
  RAISE NOTICE '';
  RAISE NOTICE '🔑 Retrieve API keys: SELECT client_name, api_key FROM api_clients;';
END $$;
