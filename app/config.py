"""Application settings."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    GOOGLE_CLIENT_SECRET_FILE: str = "client_secret.json"
    GOOGLE_TOKEN_FILE: str = "token.json"

    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: str = (
        "https://myma-acreditacion.onrender.com,http://localhost:3000,http://127.0.0.1:3000"
    )

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
