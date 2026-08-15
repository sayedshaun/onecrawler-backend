from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Config for the agent service — kept separate from src/core/config.py
    (the main API's settings) since env_prefix differs, but shares the same
    Postgres database/instance as the main backend."""

    model_config = SettingsConfigDict(
        env_file=".env", env_prefix="AGENT_", extra="ignore"
    )

    API_BASE_URL: str = "http://localhost:8000/api/v1"

    MLFLOW_TRACKING_URI: str = "http://localhost:5001"
    MLFLOW_EXPERIMENT_NAME: str = "onecrawler-agents"

    POSTGRES_USER: str = Field("onecrawler", alias="POSTGRES_USER")

    POSTGRES_PASSWORD: str = Field("onecrawler", alias="POSTGRES_PASSWORD")
    POSTGRES_DB: str = Field("onecrawler", alias="POSTGRES_DB")
    POSTGRES_HOST: str = Field("postgres", alias="POSTGRES_HOST")
    POSTGRES_PORT: int = Field(5432, alias="POSTGRES_PORT")

    @property
    def DATABASE_URL(self) -> str:
        """Built from the POSTGRES_* pieces above instead of a separate
        hardcoded connection string, so there's one source of truth."""
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def CHECKPOINTER_DSN(self) -> str:
        """langgraph-checkpoint-postgres uses psycopg directly, which doesn't
        understand SQLAlchemy's "+asyncpg" driver suffix — strip it."""
        return self.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")


settings = Settings()
