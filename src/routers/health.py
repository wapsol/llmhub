"""
Health Check Router
Provides endpoints for container health monitoring
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime
import time

from src.config.database import get_db, check_database_connection
from src.config.settings import settings
from src.models.schemas import HealthCheckResponse, DetailedHealthCheckResponse
from src.utils.logger import logger

router = APIRouter()

# Track service start time
SERVICE_START_TIME = time.time()


@router.get("/", response_model=HealthCheckResponse)
async def health_check():
    """
    Basic health check endpoint
    Returns 200 OK if service is running
    """
    return HealthCheckResponse(
        status="ok",
        timestamp=datetime.now(),
        version=settings.SERVICE_VERSION,
        uptime=time.time() - SERVICE_START_TIME
    )


@router.get("/live", response_model=DetailedHealthCheckResponse)
async def liveness_probe(db: Session = Depends(get_db)):
    """
    Kubernetes liveness probe
    Checks if the service is alive and database is accessible
    """
    checks = {}

    # Check database connection
    try:
        db_healthy = check_database_connection()
        checks["database"] = "ok" if db_healthy else "error"
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        checks["database"] = "error"

    # Check Redis (optional, won't fail if Redis is down)
    try:
        from src.config.settings import settings
        import redis
        r = redis.from_url(settings.REDIS_URL, decode_responses=True)
        r.ping()
        checks["redis"] = "ok"
    except Exception as e:
        logger.warning(f"Redis health check failed: {str(e)}")
        checks["redis"] = "degraded"

    # Determine overall status
    status = "ok" if checks.get("database") == "ok" else "error"

    return DetailedHealthCheckResponse(
        status=status,
        timestamp=datetime.now(),
        checks=checks
    )


@router.get("/ready", response_model=DetailedHealthCheckResponse)
async def readiness_probe(db: Session = Depends(get_db)):
    """
    Kubernetes readiness probe
    Checks if service is ready to accept traffic
    """
    checks = {}

    # Check database
    try:
        db_healthy = check_database_connection()
        checks["database"] = "ok" if db_healthy else "error"

        # Verify TimescaleDB extension
        result = db.execute("SELECT COUNT(*) FROM pg_extension WHERE extname = 'timescaledb'")
        timescale_installed = result.scalar() > 0
        checks["timescaledb"] = "ok" if timescale_installed else "error"

    except Exception as e:
        logger.error(f"Database readiness check failed: {str(e)}")
        checks["database"] = "error"
        checks["timescaledb"] = "error"

    # Check Redis
    try:
        import redis
        r = redis.from_url(settings.REDIS_URL, decode_responses=True)
        r.ping()
        checks["redis"] = "ok"
    except Exception as e:
        logger.error(f"Redis readiness check failed: {str(e)}")
        checks["redis"] = "error"

    # Check LLM provider API keys configured
    llm_providers_configured = 0
    if settings.OPENAI_API_KEY:
        llm_providers_configured += 1
    if settings.ANTHROPIC_API_KEY:
        llm_providers_configured += 1
    if settings.GROQ_API_KEY:
        llm_providers_configured += 1

    checks["llm_providers"] = f"{llm_providers_configured} configured"

    # Service is ready if database and TimescaleDB are OK
    all_critical_healthy = (
        checks.get("database") == "ok" and
        checks.get("timescaledb") == "ok"
    )

    status = "ready" if all_critical_healthy else "not_ready"

    return DetailedHealthCheckResponse(
        status=status,
        timestamp=datetime.now(),
        checks=checks
    )
