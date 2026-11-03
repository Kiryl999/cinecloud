from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # persistence
    database_url: str
    sql_echo: bool = False
    # Connections per process. With several replicas the sum of
    # replicas * (pool size + overflow) must stay below max_connections
    # of the database server.
    db_pool_size: int = 5
    db_max_overflow: int = 10

    # seat holds and live seat-map updates
    redis_url: str = "redis://localhost:6379/0"

    # authentication: Keycloak signs in the admins and issues their tokens,
    # the backend only verifies them - see security.py.
    # The realm's URL as the browser sees it; every token names it in `iss`.
    oidc_issuer: str
    # Where the backend itself fetches the signing keys. Empty means below the
    # issuer, which only works if the backend reaches Keycloak under the same
    # address as the browser - inside the cluster it does not.
    oidc_jwks_url: str = ""
    # set on the realm's client by an audience mapper: a token issued for
    # some other application of the realm is not accepted here
    oidc_audience: str = "cinecloud-api"

    # logging: text reads better in a terminal, JSON is what a log collector
    # can filter by field - see logs.py
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["text", "json"] = "text"


settings = Settings()
