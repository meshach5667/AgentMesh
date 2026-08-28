from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+asyncpg://agentmesh:agentmesh@localhost:5432/agentmesh"
    REDIS_URL: str = "redis://localhost:6379/0"
    SECRET_KEY: str = "supersecretkey"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    PLATFORM_FEE_RATE: float = 0.10
    HEARTBEAT_TIMEOUT_SECONDS: int = 90
    NODE_AGENT_DEFAULT_PORT: int = 8001
    API_V1_PREFIX: str = "/api/v1"
    ENVIRONMENT: str = "dev"
    LOG_LEVEL: str = "INFO"
    CORS_ORIGINS: list[str] = ["*"]

    class Config:
        env_file = ".env"


settings = Settings()
