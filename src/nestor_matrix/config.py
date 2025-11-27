"""Matrix bot configuration.

Loads settings from environment variables and .env file.
"""

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", frozen=True)

    homeserver_url: str
    user_id: str
    access_token: SecretStr
    device_id: str

    # E2EE settings
    database_url: str = "sqlite:nestor.db"
    pickle_key: SecretStr


# Global settings instance
settings = Settings()  # type: ignore[call-arg]
