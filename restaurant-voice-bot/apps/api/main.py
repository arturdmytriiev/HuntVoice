"""
FastAPI application entry point for Restaurant Voice AI Bot.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from core.settings import settings
from core.logging import setup_logging, get_logger


# Setup logging
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager.
    Handles startup and shutdown events.
    """
    # Startup
    logger.info(
        "Starting Restaurant Voice AI Bot",
        extra={
            "app_name": settings.app_name,
            "environment": settings.app_env,
            "version": "1.0.0"
        }
    )

    yield

    # Shutdown
    logger.info("Shutting down Restaurant Voice AI Bot")


# Create FastAPI application
app = FastAPI(
    title=settings.app_name,
    description="AI-powered voice assistant for restaurant operations",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": settings.app_name,
        "version": "1.0.0",
        "status": "running",
        "environment": settings.app_env
    }


@app.get("/health")
async def health_check():
    """
    Health check endpoint.
    Returns application health status.
    """
    return {
        "status": "healthy",
        "app_name": settings.app_name,
        "environment": settings.app_env
    }


@app.get("/api/v1/config")
async def get_config():
    """
    Get public configuration.
    Returns non-sensitive configuration information.
    """
    return {
        "restaurant_name": settings.restaurant_name,
        "restaurant_hours": {
            "open": settings.restaurant_hours_open,
            "close": settings.restaurant_hours_close,
            "timezone": settings.restaurant_timezone
        },
        "features": {
            "recording": settings.enable_recording,
            "transcription": settings.enable_transcription,
            "analytics": settings.enable_analytics
        }
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "apps.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_reload,
        log_level=settings.log_level.lower()
    )
