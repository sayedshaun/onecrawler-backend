from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    POSTGRES_USER: str = "onecrawler"
    POSTGRES_PASSWORD: str = "onecrawler"
    POSTGRES_DB: str = "onecrawler"
    POSTGRES_HOST: str = "postgres"
    POSTGRES_PORT: int = 5432

    REDIS_URL: str = "redis://redis:6379/0"
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    LOG_LEVEL: str = "INFO"

    JWT_SECRET_KEY: str = "dev-secret-change-me-before-deploying"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    DEFAULT_ADMIN_NAME: str = "Shaun"
    DEFAULT_ADMIN_EMAIL: str = "sayedshaun4@gmail.com"
    DEFAULT_ADMIN_PASSWORD: str = "shaun@crawler"

    MLFLOW_TRACKING_URI: str = "http://mlflow:5000"
    MLFLOW_EXPERIMENT_NAME: str = "onecrawler-agents"

    AGENT_API_BASE_URL: str = "http://localhost:8000/api/v1"

    @property
    def POSTGRES_URL(self) -> str:
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
            f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def CHECKPOINTER_DSN(self) -> str:
        """Langgraph-checkpoint-postgres uses psycopg directly, which doesn't understand
        SQLAlchemy's "+asyncpg" driver suffix — strip it."""
        return self.POSTGRES_URL.replace("postgresql+asyncpg://", "postgresql://")


settings = Settings()
