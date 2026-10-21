from typing import List, Literal

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

    # authentication
    jwt_secret: str
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    cors_origins: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # logging: text reads better in a terminal, JSON is what a log collector
    # can filter by field - see logs.py
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    log_format: Literal["text", "json"] = "text"


settings = Settings()
