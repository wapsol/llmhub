# LLMHub - Getting Started Guide

This guide will get you from zero to running LLMHub in Docker in under 5 minutes.

## Prerequisites

- Docker 20.10+ and Docker Compose 2.0+
- Node.js 18+ (for building web UI)
- At least one LLM provider API key (OpenAI, Anthropic, or Groq)

## Step-by-Step Setup

### 1. Configure Environment Variables

```bash
# Copy the example environment file
cp .env.example .env

# Edit .env and add at least one API key
nano .env  # or use your preferred editor

# Add your keys:
OPENAI_API_KEY=sk-your-openai-key-here
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key-here
GROQ_API_KEY=gsk_your-groq-key-here
```

### 2. Build the Web UI

```bash
# Navigate to web-ui directory
cd web-ui

# Install dependencies
npm install

# Build for production (outputs to web-ui/dist/)
npm run build

# Return to project root
cd ..
```

### 3. Build Docker Image

```bash
# Build the LLMHub Docker image
docker build -t llmhub:latest .

# This will take 2-3 minutes on first build
# Subsequent builds use cached layers and are much faster
```

### 4. Create and Start Containers

```bash
# Start both database and application containers
docker-compose up -d

# This command:
# - Creates llmhub-db container (TimescaleDB)
# - Creates llmhub container (FastAPI app)
# - Sets up networking between them
# - Starts both services in detached mode
```

### 5. Verify Services Are Running

```bash
# Check container status
docker-compose ps

# Expected output:
# NAME        STATUS       PORTS
# llmhub      Up           0.0.0.0:4000->4000/tcp
# llmhub-db   Up           0.0.0.0:5433->5432/tcp

# Check service health
curl http://localhost:4000/health

# Expected response:
# {"status":"healthy","service":"llm_hub","version":"1.0.0"}
```

### 6. Get Your API Keys

```bash
# Retrieve the auto-generated API keys from database
docker-compose exec llmhub-db psql -U llm_user -d llm_hub -c \
  "SELECT client_name, api_key FROM api_clients;"

# Output will show:
#        client_name        |                api_key
# ---------------------------+----------------------------------------
#  recloud-marketing         | recloud_marketing_abc123...
#  recloud-sales             | recloud_sales_xyz789...
#  recloud-email-automation  | recloud_email_def456...

# Copy one of these keys to use in API requests
```

### 7. Access the Services

**Web UI:**
```bash
# Open in browser
open http://localhost:4000

# Or manually navigate to: http://localhost:4000
```

**API Documentation:**
```bash
# Swagger UI (interactive)
open http://localhost:4000/docs

# ReDoc (read-only)
open http://localhost:4000/redoc
```

### 8. Test the API

```bash
# Replace YOUR_API_KEY with one from step 6
export API_KEY="recloud_marketing_YOUR_KEY_HERE"

# Test content generation
curl -X POST http://localhost:4000/api/v1/llm/generate-content \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Explain what LLMHub does in one sentence",
    "provider": "claude",
    "max_tokens": 100,
    "languages": ["en"]
  }'

# Expected response:
# {
#   "content": "LLMHub is a unified API service...",
#   "tokens_used": 50,
#   "cost_usd": 0.002,
#   "generation_time_ms": 1200
# }
```

---

## Common Docker Commands

### Viewing Logs

```bash
# View logs from all services
docker-compose logs

# Follow logs in real-time
docker-compose logs -f

# View logs from specific service
docker-compose logs llmhub
docker-compose logs llmhub-db

# View last 100 lines
docker-compose logs --tail=100 llmhub
```

### Managing Containers

```bash
# Stop containers (keeps data)
docker-compose stop

# Start stopped containers
docker-compose start

# Restart containers
docker-compose restart

# Stop and remove containers (keeps volumes/data)
docker-compose down

# Stop and remove everything including volumes (DELETES DATA!)
docker-compose down -v
```

### Updating the Service

```bash
# After code changes:
# 1. Rebuild web UI
cd web-ui && npm run build && cd ..

# 2. Rebuild Docker image
docker-compose build

# 3. Recreate containers
docker-compose up -d

# 4. Verify
docker-compose logs -f llmhub
```

### Database Operations

```bash
# Access database shell
docker-compose exec llmhub-db psql -U llm_user -d llm_hub

# Backup database
docker-compose exec llmhub-db pg_dump -U llm_user llm_hub > backup-$(date +%Y%m%d).sql

# Restore database
cat backup-20241027.sql | docker-compose exec -T llmhub-db psql -U llm_user -d llm_hub

# View database size
docker-compose exec llmhub-db psql -U llm_user -d llm_hub -c \
  "SELECT pg_size_pretty(pg_database_size('llm_hub'));"
```

### Image Management

```bash
# View images
docker images | grep llmhub

# Remove old image
docker rmi llmhub:latest

# Tag image for registry
docker tag llmhub:latest your-registry.com/llmhub:1.0.0

# Push to registry
docker push your-registry.com/llmhub:1.0.0

# Save image to file
docker save llmhub:latest | gzip > llmhub-latest.tar.gz

# Load image from file
docker load < llmhub-latest.tar.gz
```

---

## Complete Command Summary

```bash
# Initial Setup
cp .env.example .env                  # Configure environment
nano .env                             # Add API keys
cd web-ui && npm install && npm run build && cd ..  # Build UI
docker build -t llmhub:latest .       # Build image
docker-compose up -d                  # Start services

# Daily Use
docker-compose ps                     # Check status
docker-compose logs -f llmhub         # View logs
open http://localhost:4000            # Open web UI

# Maintenance
docker-compose restart                # Restart services
docker-compose stop                   # Stop services
docker-compose start                  # Start services
docker-compose down                   # Remove containers

# Updates
cd web-ui && npm run build && cd ..   # Rebuild UI
docker-compose build                  # Rebuild image
docker-compose up -d                  # Restart with new image

# Database
docker-compose exec llmhub-db psql -U llm_user -d llm_hub  # Access DB
docker-compose exec llmhub-db pg_dump -U llm_user llm_hub > backup.sql  # Backup
```

---

## Troubleshooting

### Port Already in Use

```bash
# Find what's using port 4000
lsof -i :4000

# Change port in docker-compose.yml
ports:
  - "8080:4000"  # Use 8080 instead
```

### Container Won't Start

```bash
# Check logs for errors
docker-compose logs llmhub

# Check database is ready
docker-compose exec llmhub-db pg_isready -U llm_user

# Restart everything
docker-compose restart
```

### Database Connection Failed

```bash
# Verify DATABASE_URL
docker-compose exec llmhub env | grep DATABASE_URL

# Verify database is running
docker-compose ps llmhub-db

# Reconnect
docker-compose restart llmhub
```

### Web UI Shows "Not Built"

```bash
# Rebuild web UI
cd web-ui
rm -rf dist node_modules
npm install
npm run build
cd ..

# Rebuild Docker image
docker-compose build llmhub

# Restart
docker-compose up -d llmhub
```

### Out of Memory

```bash
# Check resource usage
docker stats llmhub llmhub-db

# Increase Docker Desktop memory limit:
# Settings > Resources > Memory > 4GB or more
```

---

## Next Steps

1. **Read the documentation:**
   - [API Integration Guide](docs/API_INTEGRATION.md) - Integrate LLMHub into your apps
   - [Docker Setup Guide](docs/DOCKER_SETUP.md) - Advanced Docker usage
   - [Web UI Guide](docs/WEB_UI.md) - Using the management console

2. **Create API clients:**
   - Open http://localhost:4000
   - Click "API Clients" > "Create Client"
   - Copy the API key

3. **Test integrations:**
   - Try the example code in [API_INTEGRATION.md](docs/API_INTEGRATION.md)
   - Use different providers (Claude, OpenAI, Groq)
   - Monitor costs in the Billing dashboard

4. **Production deployment:**
   - Set up HTTPS with nginx/traefik
   - Configure firewall rules
   - Set up monitoring and backups
   - Review [DOCKER_SETUP.md](docs/DOCKER_SETUP.md) security section

---

## Quick Reference

| Service | URL | Purpose |
|---------|-----|---------|
| Web UI | http://localhost:4000 | Management console |
| API | http://localhost:4000/api/v1 | REST API |
| Swagger Docs | http://localhost:4000/docs | Interactive API docs |
| ReDoc | http://localhost:4000/redoc | Read-only API docs |
| Health Check | http://localhost:4000/health | Service status |
| Database | localhost:5433 | PostgreSQL/TimescaleDB |

## Support

- View logs: `docker-compose logs -f llmhub`
- Check health: `curl http://localhost:4000/health`
- API docs: http://localhost:4000/docs

For detailed documentation, see the `docs/` directory.
