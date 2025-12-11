"""Matrix bot configuration.

Loads settings from environment variables and .env file.
"""

from typing import Literal

from pydantic import Field, SecretStr
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

    # Sync behavior
    ignore_initial_sync: bool = Field(
        default=True, description="Ignore room history when first joining"
    )
    ignore_first_sync: bool = Field(
        default=False, description="Ignore events that happened during downtime"
    )

    # Néstor settings
    nestor_openai_api_key: SecretStr
    nestor_default_model: str = "gpt-4o-mini"
    nestor_search_backend: str = Field(
        default="auto",
        description="DDGS backend(s): 'auto', 'wikipedia,duckduckgo', etc.",
    )
    nestor_safesearch: Literal["on", "moderate", "off"] = Field(
        default="moderate",
        description="Safe search level: 'on', 'moderate', or 'off'",
    )


# Global settings instance
settings = Settings()  # type: ignore[call-arg]
