# LLMHub

> **Application-agnostic LLM microservice with multi-provider support, cost tracking, and web-based management**

LLMHub provides a unified API to access multiple LLM providers (Claude, OpenAI, Groq) with comprehensive billing tracking, prompt templates, and a Vue.js management console. Perfect for applications needing AI capabilities without vendor lock-in.

## ✨ Features

- 🤖 **Multi-Provider Support** - Claude, OpenAI (+ DALL-E), and Groq
- 💰 **Cost Tracking** - TimescaleDB with automatic aggregations and retention
- 🔑 **API Key Management** - Per-client keys with rate limiting and budgets
- 📝 **Prompt Templates** - Reusable templates with variable substitution
- 🎨 **Web Management UI** - Vue 3 + Vite dashboard (no authentication required)
- 📊 **Usage Analytics** - Real-time billing dashboards and cost breakdowns
- 🐳 **Docker Ready** - Complete docker-compose setup with database
- 🔄 **Translation Support** - Multi-language content generation
- 🖼️ **Image Generation** - DALL-E 3 integration

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- Node.js 18+ (for building web UI)
- At least one LLM provider API key

### 1. Clone and Configure

```bash
git clone <your-repo>
cd llm-service

# Copy and edit environment file
cp .env.example .env
# Add your API keys to .env:
# OPENAI_API_KEY=sk-...
# ANTHROPIC_API_KEY=sk-ant-...
# GROQ_API_KEY=gsk_...
```

### 2. Build Web UI

```bash
cd web-ui
npm install
npm run build
cd ..
```

### 3. Start Services

```bash
# Start database and application
docker-compose up -d

# View logs
docker-compose logs -f llmhub

# Check health
curl http://localhost:4000/health
```

### 4. Get API Keys

```bash
docker-compose exec llmhub-db psql -U llm_user -d llm_hub -c \
  "SELECT client_name, api_key FROM api_clients;"
```

### 5. Access Points

- **Web UI:** http://localhost:4000
- **API Docs (Swagger):** http://localhost:4000/docs
- **API Docs (ReDoc):** http://localhost:4000/redoc

## 📖 Documentation

- **[API Integration Guide](docs/API_INTEGRATION.md)** - How to integrate LLMHub into your applications
- **[Docker Setup Guide](docs/DOCKER_SETUP.md)** - Complete Docker commands and deployment
- **[Web UI Guide](docs/WEB_UI.md)** - Using the management console
- **[CLAUDE.md](CLAUDE.md)** - Developer guide for Claude Code

## 🎯 Usage Examples

### Python

```python
import requests

response = requests.post(
    "http://localhost:4000/api/v1/llm/generate-content",
    headers={"X-API-Key": "your-api-key"},
    json={
        "prompt": "Explain quantum computing in simple terms",
        "provider": "claude",
        "max_tokens": 500,
        "languages": ["en"]
    }
)

content = response.json()["content"]
cost = response.json()["cost_usd"]
print(f"Generated content (${cost}):\n{content}")
```

### JavaScript

```javascript
const axios = require('axios');

const response = await axios.post(
  'http://localhost:4000/api/v1/llm/generate-content',
  {
    prompt: 'Explain quantum computing in simple terms',
    provider: 'claude',
    max_tokens: 500,
    languages: ['en']
  },
  {
    headers: { 'X-API-Key': 'your-api-key' }
  }
);

console.log(response.data.content);
console.log(`Cost: $${response.data.cost_usd}`);
```

### cURL

```bash
curl -X POST http://localhost:4000/api/v1/llm/generate-content \
  -H "X-API-Key: your-api-key" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Explain quantum computing in simple terms",
    "provider": "claude",
    "max_tokens": 500,
    "languages": ["en"]
  }'
```

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  Client Applications                     │
│  (Your marketing app, sales tool, automation, etc.)     │
└───────────────────┬─────────────────────────────────────┘
                    │ HTTP REST API + API Key
┌───────────────────▼─────────────────────────────────────┐
│                   LLMHub Service                         │
│  ┌────────────────────────────────────────────────┐    │
│  │ FastAPI Application                             │    │
│  ├────────────────────────────────────────────────┤    │
│  │ • API Key Authentication                        │    │
│  │ • Multi-Provider Routing (Claude/OpenAI/Groq)  │    │
│  │ • Prompt Template Engine                        │    │
│  │ • Cost Calculation & Logging                    │    │
│  │ • Vue.js Management UI                          │    │
│  └────────────────────────────────────────────────┘    │
└───────────────────┬─────────────────────────────────────┘
                    │
        ┌───────────┴──────────┬──────────────┐
        │                      │              │
        ▼                      ▼              ▼
┌──────────────┐      ┌──────────────┐   ┌────────────┐
│ Anthropic    │      │   OpenAI     │   │    Groq    │
│   Claude     │      │ GPT-4+DALL-E │   │  Mixtral   │
└──────────────┘      └──────────────┘   └────────────┘

        ▼
┌─────────────────────────────────────────────────────────┐
│              TimescaleDB Database                        │
│  • API Clients & Keys                                    │
│  • Prompt Templates & Versions                           │
│  • LLM Generation Logs (Hypertable)                      │
│  • Cost Aggregations (Hourly/Daily/Monthly)              │
│  • 90-day Retention Policy                               │
└─────────────────────────────────────────────────────────┘
```

## 💾 Database Schema

- **`api_clients`** - Registered API clients with keys and budgets
- **`prompt_templates`** - Reusable prompts with variables
- **`prompt_versions`** - Version history for A/B testing
- **`llm_generation_log`** - Time-series data (hypertable) with cost tracking
- **Continuous Aggregations:** `llm_hourly_costs`, `llm_daily_costs`, `llm_monthly_billing`

## 🔧 Development

### Local Development (without Docker)

```bash
# Install Python dependencies
pip install -r requirements.txt

# Start database
docker-compose up -d llmhub-db

# Run development server
uvicorn src.main:app --reload --port 4000

# In another terminal, run web UI dev server
cd web-ui
npm run dev  # Opens on http://localhost:5173
```

### Running Tests

```bash
# Run all tests
pytest tests/

# With coverage
pytest tests/ --cov=src --cov-report=html

# Type checking
mypy src/

# Linting
flake8 src/ tests/

# Format code
black src/ tests/
```

## 🐳 Docker Commands

### Build and Run

```bash
# Build Docker image
docker build -t llmhub:latest .

# Start with docker-compose (recommended)
docker-compose up -d

# Stop services
docker-compose down

# View logs
docker-compose logs -f llmhub

# Rebuild after code changes
docker-compose build
docker-compose up -d
```

### Database Management

```bash
# Access database
docker-compose exec llmhub-db psql -U llm_user -d llm_hub

# Backup database
docker-compose exec llmhub-db pg_dump -U llm_user llm_hub > backup.sql

# Restore database
cat backup.sql | docker-compose exec -T llmhub-db psql -U llm_user -d llm_hub

# View database size
docker-compose exec llmhub-db psql -U llm_user -d llm_hub -c \
  "SELECT pg_size_pretty(pg_database_size('llm_hub'));"
```

## 📊 Cost Tracking

Every LLM API call is logged with:

- Input/output token counts
- Calculated costs (per provider/model)
- Generation time
- Success/failure status
- Request metadata

**Automatic Aggregations:**

- **Hourly** - Refreshed every hour
- **Daily** - Refreshed every 4 hours
- **Monthly** - Refreshed weekly

**Retention:** Raw logs kept for 90 days, aggregations kept forever.

## 🔐 Security Considerations

- **API Keys:** Stored in plaintext in database (consider hashing for production)
- **No Web UI Auth:** Designed for internal networks only
- **CORS:** Configure `CORS_ORIGINS` in `.env` for your frontends
- **Rate Limiting:** Configured per client, enforced at application level
- **Budgets:** Monthly limits can be set but aren't hard-enforced yet

**Production Recommendations:**

- Run behind firewall or VPN
- Use HTTPS with reverse proxy (nginx/traefik)
- Change default database password
- Rotate API keys regularly
- Set up monitoring and alerts

## 🌍 Environment Variables

**Required:**

```bash
DATABASE_URL=postgresql://llm_user:password@llmhub-db:5432/llm_hub
OPENAI_API_KEY=sk-...        # Optional if not using OpenAI
ANTHROPIC_API_KEY=sk-ant-... # Optional if not using Claude
GROQ_API_KEY=gsk_...         # Optional if not using Groq
```

**Optional:**

```bash
SERVICE_NAME=llm_hub
LOG_LEVEL=info
DEFAULT_PROVIDER=claude
DEFAULT_MODEL=claude-3-5-sonnet-20241022
CORS_ORIGINS=http://localhost:3000,http://localhost:5173
```

See `.env.example` for complete list.

## 🤝 Contributing

This is an internal project. For changes:

1. Create feature branch
2. Make changes with tests
3. Run linting and type checks
4. Submit for review

## 📝 License

UNLICENSED - Internal project

## 🆘 Troubleshooting

**Service won't start:**
```bash
docker-compose logs llmhub  # Check logs
docker-compose restart      # Restart services
```

**Web UI not loading:**
```bash
cd web-ui && npm run build && cd ..  # Rebuild UI
docker-compose build llmhub          # Rebuild image
docker-compose up -d
```

**Database connection issues:**
```bash
docker-compose exec llmhub-db pg_isready -U llm_user  # Check DB
docker-compose exec llmhub env | grep DATABASE_URL     # Check URL
```

**API calls failing:**
- Check API key is valid (Web UI > API Clients)
- Verify provider API key in `.env`
- Check rate limit not exceeded
- Review logs: `docker-compose logs -f llmhub`

## 📚 API Endpoints

### Core Endpoints

- `POST /api/v1/llm/generate-content` - Generate text content
- `POST /api/v1/llm/translate` - Translate to multiple languages
- `POST /api/v1/llm/generate-image` - Generate images (DALL-E)
- `POST /api/v1/llm/improve-content` - Enhance existing content

### Admin Endpoints (for Web UI)

- `GET /api/v1/admin/stats` - Dashboard statistics
- `GET /api/v1/admin/providers` - Provider configuration status
- `GET /api/v1/admin/clients` - List API clients
- `POST /api/v1/admin/clients` - Create API client
- `GET /api/v1/admin/billing/*` - Billing data

### Health & Docs

- `GET /health` - Basic health check
- `GET /health/live` - Liveness probe
- `GET /health/ready` - Readiness probe
- `GET /docs` - Swagger UI
- `GET /redoc` - ReDoc UI

See full API documentation at http://localhost:4000/docs

## 🎉 What's Next?

Future enhancements:

- [ ] Web UI authentication system
- [ ] Hard budget enforcement
- [ ] Webhook notifications for budget alerts
- [ ] Caching layer (Redis)
- [ ] Streaming responses
- [ ] More LLM providers (Cohere, Mistral)
- [ ] Prompt versioning UI
- [ ] Cost forecasting

## 📞 Support

- **Web UI:** http://localhost:4000
- **API Docs:** http://localhost:4000/docs
- **Logs:** `docker-compose logs -f llmhub`
- **Health:** `curl http://localhost:4000/health`

For documentation, see the `docs/` directory.

---

**Built with:** Python, FastAPI, Vue 3, TimescaleDB, Docker

**Version:** 1.0.0
