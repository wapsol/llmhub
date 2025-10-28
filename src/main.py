"""
LLM Microservice - FastAPI Application
Application-agnostic LLM service with billing tracking
"""

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import time
import os
from pathlib import Path

from src.config.settings import settings
from src.config.database import init_database, close_database
from src.utils.logger import logger
from src.routers import health

# Import routers
from src.routers import content, images, prompts, billing, admin


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager
    Handles startup and shutdown events
    """
    # Startup
    logger.info(f"Starting {settings.SERVICE_NAME} v{settings.SERVICE_VERSION}")

    try:
        await init_database()
        logger.info("✅ Database initialized")
    except Exception as e:
        logger.error(f"❌ Failed to initialize database: {str(e)}")
        raise

    logger.info(f"🎯 Service ready on port 4000")
    logger.info(f"📚 API Documentation: http://localhost:4000/docs")

    yield  # Application runs here

    # Shutdown
    logger.info("👋 Shutting down service")
    await close_database()
    logger.info("✅ Shutdown complete")


# ============================================================================
# FastAPI Application
# ============================================================================

app = FastAPI(
    title=settings.SERVICE_NAME,
    description="Application-agnostic LLM service with multi-provider support and billing tracking",
    version=settings.SERVICE_VERSION,
    docs_url=settings.DOCS_URL,
    redoc_url=settings.REDOC_URL,
    openapi_url=settings.OPENAPI_URL,
    lifespan=lifespan
)

# ============================================================================
# CORS Middleware
# ============================================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.CORS_ALLOW_METHODS,
    allow_headers=settings.CORS_ALLOW_HEADERS,
)

# ============================================================================
# Request Logging Middleware
# ============================================================================

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all HTTP requests with timing"""
    start_time = time.time()

    # Process request
    response = await call_next(request)

    # Calculate duration
    duration_ms = int((time.time() - start_time) * 1000)

    # Log request
    logger.info(
        "http_request",
        method=request.method,
        path=request.url.path,
        status_code=response.status_code,
        duration_ms=duration_ms,
        client_host=request.client.host if request.client else None
    )

    # Add custom headers
    response.headers["X-Process-Time"] = str(duration_ms)
    response.headers["X-Service-Version"] = settings.SERVICE_VERSION

    return response


# ============================================================================
# Exception Handlers
# ============================================================================

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors with detailed messages"""
    logger.warning(
        "validation_error",
        path=request.url.path,
        errors=exc.errors()
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "success": False,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Invalid request parameters",
                "details": exc.errors()
            }
        }
    )


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle unexpected errors"""
    logger.error(
        "unhandled_exception",
        path=request.url.path,
        error=str(exc),
        exc_info=True
    )

    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "An unexpected error occurred"
            }
        }
    )


# ============================================================================
# Register Routers
# ============================================================================

# Health check endpoints
app.include_router(
    health.router,
    prefix="/health",
    tags=["Health"]
)

# Content generation endpoints
app.include_router(
    content.router,
    prefix="/api/v1/llm",
    tags=["Content Generation"]
)

# Image generation endpoints
app.include_router(
    images.router,
    prefix="/api/v1/llm",
    tags=["Image Generation"]
)

# Prompt library endpoints
app.include_router(
    prompts.router,
    prefix="/api/v1/llm/prompts",
    tags=["Prompt Library"]
)

# Billing endpoints
app.include_router(
    billing.router,
    prefix="/api/v1/llm/billing",
    tags=["Billing"]
)

# Admin endpoints (for web UI)
app.include_router(
    admin.router,
    prefix="/api/v1/admin",
    tags=["Admin"]
)


# ============================================================================
# Static Files & Web UI
# ============================================================================

# Mount static files for web UI
web_ui_path = Path(__file__).parent.parent / "web-ui" / "dist"
if web_ui_path.exists():
    app.mount("/assets", StaticFiles(directory=str(web_ui_path / "assets")), name="assets")
    logger.info("✅ Web UI static files mounted")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        """
        Serve the Vue.js SPA
        All non-API routes serve index.html for client-side routing
        """
        # API routes should not be caught by this
        if full_path.startswith(("api/", "health", "docs", "redoc", "openapi.json")):
            return JSONResponse(
                status_code=404,
                content={"detail": "Not found"}
            )

        # Check if file exists in web-ui/dist
        file_path = web_ui_path / full_path

        if file_path.is_file():
            return FileResponse(file_path)

        # For all other routes, serve index.html (SPA routing)
        index_path = web_ui_path / "index.html"
        if index_path.exists():
            return FileResponse(index_path)

        # Fallback if no web UI is built
        return JSONResponse(
            status_code=200,
            content={
                "service": settings.SERVICE_NAME,
                "version": settings.SERVICE_VERSION,
                "status": "operational",
                "message": "Web UI not built. Run: cd web-ui && npm install && npm run build",
                "documentation": {
                    "swagger": f"{settings.DOCS_URL}",
                    "redoc": f"{settings.REDOC_URL}",
                    "openapi": f"{settings.OPENAPI_URL}"
                },
                "health_checks": {
                    "basic": "/health",
                    "liveness": "/health/live",
                    "readiness": "/health/ready"
                }
            }
        )
else:
    logger.warning("⚠️  Web UI dist folder not found. Run: cd web-ui && npm install && npm run build")

    @app.get("/", include_in_schema=False)
    async def root():
        """Root endpoint with service information"""
        return {
            "service": settings.SERVICE_NAME,
            "version": settings.SERVICE_VERSION,
            "status": "operational",
            "message": "Web UI not built. Run: cd web-ui && npm install && npm run build",
            "documentation": {
                "swagger": f"{settings.DOCS_URL}",
                "redoc": f"{settings.REDOC_URL}",
                "openapi": f"{settings.OPENAPI_URL}"
            },
            "health_checks": {
                "basic": "/health",
                "liveness": "/health/live",
                "readiness": "/health/ready"
            }
        }


# ============================================================================
# Prometheus Metrics Endpoint (Optional - for future)
# ============================================================================

# from prometheus_client import make_asgi_app
# metrics_app = make_asgi_app()
# app.mount("/metrics", metrics_app)
