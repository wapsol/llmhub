# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**LLMHub** is a Python FastAPI-based LLM microservice that provides application-agnostic LLM capabilities with multi-provider support (Claude, OpenAI, Groq) and comprehensive billing tracking using TimescaleDB. The service includes a Vue 3 + Vite web management console for API key management, provider configuration, and usage analytics.

**Current Status**: Fully functional with multi-provider integration, cost tracking, prompt templates, and a complete web UI for management. Ready for production deployment with Docker.

## Development Commands

### Running the Service

```bash
# Start service and database with Docker
docker-compose up -d

# Watch logs
docker-compose logs -f llmhub

# Stop services
docker-compose down
```

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Run development server (requires .env configuration)
uvicorn src.main:app --reload --host 0.0.0.0 --port 4000

# Run with specific log level
uvicorn src.main:app --reload --log-level debug
```

### Testing and Code Quality

```bash
# Run tests (when implemented)
pytest tests/

# Run tests with coverage
pytest tests/ --cov=src --cov-report=html

# Type checking
mypy src/

# Code formatting
black src/ tests/

# Linting
flake8 src/ tests/
```

### Database Operations

```bash
# Access database shell
docker-compose exec llmhub-db psql -U llm_user -d llm_hub

# Retrieve seeded API keys
docker-compose exec llmhub-db psql -U llm_user -d llm_hub -c \
  "SELECT client_name, api_key FROM api_clients;"

# View prompt templates
docker-compose exec llmhub-db psql -U llm_user -d llm_hub -c \
  "SELECT template_name, template_type FROM prompt_templates;"

# Check generation logs
docker-compose exec llmhub-db psql -U llm_user -d llm_hub -c \
  "SELECT * FROM llm_generation_log ORDER BY created_at DESC LIMIT 10;"

# View cost aggregations
docker-compose exec llmhub-db psql -U llm_user -d llm_hub -c \
  "SELECT * FROM llm_daily_costs ORDER BY day DESC LIMIT 7;"
```

### API Testing

```bash
# Health check
curl http://localhost:4000/health

# View API documentation
open http://localhost:4000/docs  # Swagger UI
open http://localhost:4000/redoc # ReDoc

# Test authenticated endpoint (replace with actual API key)
curl -X POST http://localhost:4000/api/v1/llm/generate-content \
  -H "X-API-Key: recloud_marketing_your-key-here" \
  -H "Content-Type: application/json" \
  -d '{"prompt": "Test", "languages": ["en"], "provider": "claude"}'
```

## Architecture Overview

### High-Level Flow

1. **Client Applications** (Marketing Admin, Sales Admin, Email Automation) make HTTP requests to the LLM service
2. **FastAPI Application** (`src/main.py`) handles routing, middleware, and exception handling
3. **Authentication** (`src/services/auth.py`) validates API keys via `X-API-Key` header against `api_clients` table
4. **Routers** (`src/routers/`) handle endpoint-specific logic and validation
5. **Services** (`src/services/`) contain business logic:
   - `llm_core.py`: Multi-provider LLM API integration
   - `billing.py`: Cost tracking and logging to TimescaleDB
   - `auth.py`: API key validation
6. **Database** (TimescaleDB): Stores templates, logs all LLM calls with time-series data, and maintains continuous aggregations for billing

### Key Design Patterns

**Multi-Provider LLM Abstraction**: `LLMCoreService` provides a unified interface for calling Claude, OpenAI, and Groq. Each provider has a private method (`_call_claude`, `_call_openai`, `_call_groq`) that handles provider-specific API formatting while the public `call_llm` method provides a consistent interface.

**Cost Tracking Architecture**: Every LLM API call is logged to `llm_generation_log` (TimescaleDB hypertable) with:
- Input/output token counts
- Calculated costs based on provider pricing (configured in `settings.py`)
- Generation time, success status, and metadata
- Continuous aggregations automatically compute hourly/daily/monthly costs

**API Key Authentication**: All LLM endpoints require `X-API-Key` header. The `get_current_client` dependency (from `src/services/auth.py`) validates keys and injects the authenticated `APIClient` object into route handlers.

**Prompt Template System**: Reusable templates stored in `prompt_templates` table with:
- Variable substitution support (JSONB `variables` field)
- Version history in `prompt_versions` for A/B testing
- Usage tracking (`usage_count`, `success_rate`) for optimization
- System templates (owner_client_id=NULL) vs client-specific templates

## Important Implementation Details

### Database Schema

The database uses TimescaleDB for time-series optimization:

- **`api_clients`**: Registered API clients with keys, rate limits, and budget tracking
- **`prompt_templates`**: Reusable prompt templates with variable substitution
- **`prompt_versions`**: Version history for A/B testing
- **`llm_generation_log`**: Hypertable (partitioned by `created_at`) logging all LLM calls with cost data
- **Continuous Aggregations**: `llm_hourly_costs`, `llm_daily_costs`, `llm_monthly_costs` (materialized views)
- **Retention Policy**: Automatically drops data older than 90 days from `llm_generation_log`

### Configuration Management

All settings in `src/config/settings.py` use Pydantic Settings:

- Environment variables loaded from `.env` file
- Type validation and parsing automatic
- Cost tracking rates (USD per 1K tokens) configured per model
- Helper methods: `get_cost_per_1k_tokens()`, `get_dalle_cost()`

### LLM Provider Integration

Located in `src/services/llm_core.py`:

- Synchronous clients initialized in `__init__` if API keys present
- `call_llm()` method routes to appropriate provider
- Token counting via `tiktoken` (OpenAI's tokenizer)
- Cost calculation happens in provider-specific methods
- Returns unified response format: `{content, input_tokens, output_tokens, cost_usd, generation_time_ms}`

### Error Handling

- Request validation errors return 422 with detailed field errors
- Authentication errors return 401 (invalid key) or 403 (inactive client)
- LLM API errors are logged with full context and re-raised
- Global exception handler catches unexpected errors and returns 500

## File Organization

```
llm-service/
├── src/
│   ├── main.py                    # FastAPI app, middleware, router registration, static file serving
│   ├── config/
│   │   ├── settings.py           # Pydantic settings with cost tracking config
│   │   └── database.py           # SQLAlchemy setup, connection management
│   ├── models/
│   │   ├── database.py           # SQLAlchemy ORM models (APIClient, PromptTemplate, etc.)
│   │   └── schemas.py            # Pydantic request/response schemas
│   ├── routers/
│   │   ├── health.py             # Health check endpoints
│   │   ├── content.py            # Content generation endpoints
│   │   ├── images.py             # Image generation endpoints
│   │   ├── prompts.py            # Prompt library CRUD
│   │   ├── billing.py            # Billing reports
│   │   └── admin.py              # Admin endpoints for web UI
│   ├── services/
│   │   ├── llm_core.py           # Multi-provider LLM integration (core logic)
│   │   ├── auth.py               # API key validation
│   │   └── billing.py            # Cost tracking and logging
│   └── utils/
│       └── logger.py             # Structured logging with structlog
├── web-ui/                        # Vue 3 + Vite management console
│   ├── src/
│   │   ├── main.js               # Vue app initialization with router
│   │   ├── App.vue               # Main app component with navigation
│   │   ├── style.css             # Tailwind CSS styles
│   │   ├── api/
│   │   │   └── client.js         # Axios API client
│   │   ├── views/                # Page components
│   │   │   ├── DashboardView.vue
│   │   │   ├── ProvidersView.vue
│   │   │   ├── APIClientsView.vue
│   │   │   ├── TemplatesView.vue
│   │   │   └── BillingView.vue
│   │   └── components/           # Reusable components
│   ├── index.html                # HTML entry point
│   ├── package.json              # Node.js dependencies
│   ├── vite.config.js            # Vite build configuration
│   └── tailwind.config.js        # Tailwind CSS configuration
├── docs/                          # Documentation
│   ├── API_INTEGRATION.md        # Integration guide for developers
│   ├── DOCKER_SETUP.md           # Docker commands and deployment
│   └── WEB_UI.md                 # Web UI usage guide
├── database/
│   └── init.sql                  # TimescaleDB schema with hypertables and aggregations
├── tests/                        # Test directory
├── requirements.txt              # Python dependencies
├── Dockerfile                    # Container configuration
├── docker-compose.yml            # Complete stack (database + app)
├── .dockerignore                 # Docker build exclusions
├── .env.example                  # Environment variable template
├── CLAUDE.md                     # This file
└── README.md                     # Project documentation
```

## Common Development Workflows

### Adding a New LLM Endpoint

1. Define Pydantic request/response schemas in `src/models/schemas.py`
2. Add route handler in appropriate router (e.g., `src/routers/content.py`)
3. Use `get_current_client` dependency for authentication
4. Call `llm_core.call_llm()` for LLM generation
5. Log result to database using `billing_service.log_generation()`
6. Return standardized response with cost tracking

### Adding a New LLM Provider

1. Add API key setting in `src/config/settings.py` (e.g., `COHERE_API_KEY`)
2. Add cost rates per 1K tokens in Settings class
3. Update `get_cost_per_1k_tokens()` method with new provider logic
4. Initialize client in `LLMCoreService.__init__()` in `src/services/llm_core.py`
5. Implement private method (e.g., `_call_cohere()`) following existing patterns
6. Add provider case in `call_llm()` routing logic

### Modifying Cost Tracking

Cost rates are defined in `src/config/settings.py` as class attributes. To update pricing:

1. Modify the appropriate constant (e.g., `ANTHROPIC_CLAUDE_SONNET_INPUT_COST`)
2. Update `.env` file if using environment variable overrides
3. Restart service to pick up new rates

The `get_cost_per_1k_tokens()` method maps model names to cost rates using string matching (e.g., "sonnet" in model name → Sonnet pricing).

### Database Migrations

This project does NOT currently use Alembic or automated migrations. Schema changes are manual:

1. Update `database/init.sql` with new schema
2. Update SQLAlchemy models in `src/models/database.py` to match
3. For existing deployments, write manual migration SQL
4. Test against a copy of production data first

## Environment Variables

Required variables (see `.env.example`):

- `DATABASE_URL`: PostgreSQL connection string for TimescaleDB
- `OPENAI_API_KEY`: OpenAI API key (optional if not using OpenAI)
- `ANTHROPIC_API_KEY`: Anthropic API key (optional if not using Claude)
- `GROQ_API_KEY`: Groq API key (optional if not using Groq)

Cost tracking variables define USD per 1K tokens for each model. These can be overridden via environment variables to update pricing without code changes.

## Security Considerations

- API keys are stored in plaintext in database (consider hashing for production)
- All LLM endpoints require `X-API-Key` header authentication
- CORS origins configured in settings (default: localhost:3000, localhost:5173)
- Rate limiting configured per client but not yet implemented in middleware
- Monthly budget limits stored but not enforced (future feature)

## Troubleshooting

**Service won't start**: Check that `DATABASE_URL` is correct and database is accessible. View logs with `docker-compose logs llm-service`.

**Authentication fails**: Verify API key exists in database and `is_active=true`. Retrieve keys with database query shown in "Database Operations" section.

**LLM calls fail**: Check that provider API keys are set in `.env` and valid. View detailed error logs in service output.

**High costs**: Query `llm_daily_costs` continuous aggregation to see cost breakdown by provider. Consider switching to cheaper models (Groq is much cheaper than OpenAI).

**Database query performance**: TimescaleDB automatically partitions `llm_generation_log` by time. Queries should include time range filters to leverage partitioning. Continuous aggregations provide pre-computed metrics.
