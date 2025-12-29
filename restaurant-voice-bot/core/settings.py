"""
Application settings and configuration management using Pydantic Settings.
"""
from typing import List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from datetime import time


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )

    # Application Settings
    app_name: str = Field(default="Restaurant Voice Bot", description="Application name")
    app_env: str = Field(default="development", description="Environment (development, staging, production)")
    debug: bool = Field(default=False, description="Debug mode")
    log_level: str = Field(default="INFO", description="Logging level")

    # Database Configuration
    postgres_user: str = Field(default="postgres", description="PostgreSQL username")
    postgres_password: str = Field(default="postgres", description="PostgreSQL password")
    postgres_db: str = Field(default="restaurant_bot", description="PostgreSQL database name")
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/restaurant_bot",
        description="Database connection URL"
    )

    # Redis Configuration
    redis_url: str = Field(default="redis://localhost:6379/0", description="Redis connection URL")
    redis_max_connections: int = Field(default=10, description="Maximum Redis connections")

    # Restaurant Configuration
    restaurant_name: str = Field(default="My Restaurant", description="Restaurant name")
    restaurant_hours_open: str = Field(default="09:00", description="Opening time (HH:MM)")
    restaurant_hours_close: str = Field(default="22:00", description="Closing time (HH:MM)")
    restaurant_timezone: str = Field(default="America/New_York", description="Restaurant timezone")
    restaurant_phone: str = Field(default="+1234567890", description="Restaurant phone number")

    # Twilio Configuration
    twilio_account_sid: str = Field(default="", description="Twilio Account SID")
    twilio_auth_token: str = Field(default="", description="Twilio Auth Token")
    twilio_phone_number: str = Field(default="", description="Twilio phone number")

    # OpenAI Configuration
    openai_api_key: str = Field(default="", description="OpenAI API key")
    openai_model: str = Field(default="gpt-4-turbo-preview", description="OpenAI model to use")
    openai_temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Model temperature")

    # LangGraph Configuration
    langgraph_checkpoint_store: str = Field(default="redis", description="LangGraph checkpoint storage")

    # API Configuration
    api_host: str = Field(default="0.0.0.0", description="API host")
    api_port: int = Field(default=8000, ge=1, le=65535, description="API port")
    api_workers: int = Field(default=4, ge=1, description="Number of API workers")
    api_reload: bool = Field(default=False, description="Enable auto-reload")

    # CORS Settings
    cors_origins: str = Field(
        default="http://localhost:3000,http://localhost:8000",
        description="Allowed CORS origins (comma-separated)"
    )
    cors_allow_credentials: bool = Field(default=True, description="Allow credentials in CORS")

    # Session Configuration
    session_timeout_minutes: int = Field(default=30, ge=1, description="Session timeout in minutes")
    max_conversation_turns: int = Field(default=50, ge=1, description="Maximum conversation turns")

    # Webhook URLs
    webhook_base_url: str = Field(default="https://your-domain.com", description="Base webhook URL")
    twilio_webhook_path: str = Field(default="/api/v1/twilio/voice", description="Twilio webhook path")

    # Feature Flags
    enable_recording: bool = Field(default=False, description="Enable call recording")
    enable_transcription: bool = Field(default=True, description="Enable transcription")
    enable_analytics: bool = Field(default=True, description="Enable analytics")

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is one of the allowed values."""
        allowed_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        v_upper = v.upper()
        if v_upper not in allowed_levels:
            raise ValueError(f"log_level must be one of {allowed_levels}")
        return v_upper

    @field_validator("app_env")
    @classmethod
    def validate_app_env(cls, v: str) -> str:
        """Validate environment is one of the allowed values."""
        allowed_envs = ["development", "staging", "production"]
        v_lower = v.lower()
        if v_lower not in allowed_envs:
            raise ValueError(f"app_env must be one of {allowed_envs}")
        return v_lower

    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string to list."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.app_env == "production"

    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.app_env == "development"

    @property
    def twilio_webhook_url(self) -> str:
        """Get full Twilio webhook URL."""
        return f"{self.webhook_base_url.rstrip('/')}{self.twilio_webhook_path}"


# Global settings instance
settings = Settings()
