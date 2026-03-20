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

    # Fallback-postboks hvis Graph-notification mangler parsebar 'resource' / @odata.id
    # (f.eks. Salg@arcticmotor.no). Bruk helst at webhook inneholder full ressurssti.
    graph_default_mailbox: str | None = None

    # Graph webhooks / subscription-fornyelse
    # Full offentlig URL til webhook (brukes til å filtrere hvilke subscriptions som fornyes),
    # f.eks. https://arcticemailagent.sliplane.app/graph/webhook
    graph_webhook_url: str | None = None
    graph_subscription_renew_enabled: bool = True
    graph_subscription_renew_interval_seconds: int = 21600  # 6 timer
    # Maks ca. 4230 min for postboks-meldinger; hold litt margin under taket
    graph_subscription_extend_minutes: int = 4180

    # Unngå duplikat-behandling av samme melding (spar Claude-tokens)
    # Kun kjør pipeline for notifications med created; ignorer rent «updated».
    graph_webhook_only_created: bool = True
    # Sekunder: ikke prosesser samme message_id på nytt (default 24t)
    graph_webhook_message_dedupe_ttl_seconds: int = 86400

    # Misc
    environment: str = "local"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()

