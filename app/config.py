from functools import lru_cache
from pydantic import AnyHttpUrl
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "Arctic Email Assistant"

    # Claude / Anthropic
    claude_api_key: str | None = None
    claude_model: str = "claude-sonnet-4-6"

    # Microsoft Graph / Azure AD
    graph_tenant_id: str | None = None
    graph_client_id: str | None = None
    graph_client_secret: str | None = None
    graph_base_url: AnyHttpUrl = "https://graph.microsoft.com/v1.0"  # type: ignore[assignment]

    # Misc
    environment: str = "local"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()

