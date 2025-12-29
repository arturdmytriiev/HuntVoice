"""Application configuration settings."""

from typing import Optional
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    APP_NAME: str = "Voice AI Restaurant Bot"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # Database
    DATABASE_URL: str = "sqlite:///./restaurant_bot.db"

    # Twilio
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_PHONE_NUMBER: Optional[str] = None

    # Restaurant Configuration
    RESTAURANT_NAME: str = "Hunt Restaurant"
    RESTAURANT_PHONE: str = "+1234567890"

    # Menu File Path
    MENU_FILE_PATH: str = "data/menu.json"

    # Voice Settings
    VOICE_LANGUAGE: str = "en-US"
    VOICE_TYPE: str = "Polly.Joanna"

    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
