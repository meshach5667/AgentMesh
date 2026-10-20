from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

INSECURE_DEFAULT_SECRET = "supersecretkey"
DEV_ENVIRONMENTS = {"dev", "development", "test", "testing"}


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[3] / ".env"),
        extra="ignore",
    )

    DATABASE_URL: str = "postgresql+asyncpg://agentmesh:agentmesh@localhost:5432/agentmesh"
    REDIS_URL: str = "redis://localhost:6379/0"
    SECRET_KEY: str = INSECURE_DEFAULT_SECRET
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    PLATFORM_FEE_RATE: float = 0.10
    HEARTBEAT_TIMEOUT_SECONDS: int = 90
    NODE_AGENT_DEFAULT_PORT: int = 8001
    CONTROL_PLANE_URL: str = "http://localhost:8000"
    NODE_AGENT_PORT: int = 8001
    POSTGRES_DB: str = "agentmesh"
    POSTGRES_USER: str = "agentmesh"
    POSTGRES_PASSWORD: str = "agentmesh"
    NEXT_PUBLIC_API_URL: str = "http://localhost:8000/api/v1"
    API_V1_PREFIX: str = "/api/v1"
    ENVIRONMENT: str = "dev"
    LOG_LEVEL: str = "INFO"
    # Explicit origins only: credentials are allowed, so a wildcard would be unsafe.
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]
    # Unpaid "test credits" for local development. Never honoured outside dev/test environments.
    ALLOW_TEST_CREDITS: bool = True
    SQL_ECHO: bool = False

    # Public base URL customers use to reach the gateway (used to build deployment endpoints).
    PUBLIC_BASE_URL: str = "http://localhost:8000"

    # Worker protocol
    WORKER_PROTOCOL_VERSIONS: list[int] = [1]
    WORKER_HEARTBEAT_INTERVAL_SECONDS: int = 15
    ENROLLMENT_TOKEN_TTL_MINUTES: int = 60
    COMMAND_LEASE_SECONDS: int = 60
    COMMAND_MAX_ATTEMPTS: int = 3
    WORKER_MAX_BODY_BYTES: int = 256 * 1024

    # Deployment lifecycle timeouts
    PROVISION_STALL_TIMEOUT_SECONDS: int = 900  # no progress report for this long -> FAILED
    PROVISION_MAX_SECONDS: int = 3600
    STOP_TIMEOUT_SECONDS: int = 300
    UNHEALTHY_GRACE_SECONDS: int = 900
    MONITOR_INTERVAL_SECONDS: int = 15
    BACKGROUND_JOBS_ENABLED: bool = True

    # Inference gateway
    GATEWAY_MAX_BODY_BYTES: int = 1024 * 1024
    GATEWAY_RATE_LIMIT_PER_MINUTE: int = 60
    GATEWAY_MAX_CONCURRENT_PER_DEPLOYMENT: int = 4
    GATEWAY_FIRST_BYTE_TIMEOUT_SECONDS: int = 180
    GATEWAY_IDLE_TIMEOUT_SECONDS: int = 120
    GATEWAY_MAX_RESPONSE_BYTES: int = 32 * 1024 * 1024

    @property
    def is_dev(self) -> bool:
        return self.ENVIRONMENT.lower() in DEV_ENVIRONMENTS

    @property
    def test_credits_enabled(self) -> bool:
        return self.is_dev and self.ALLOW_TEST_CREDITS

    @model_validator(mode="after")
    def _check_production_safety(self) -> "Settings":
        if not self.is_dev:
            if (
                self.SECRET_KEY in (INSECURE_DEFAULT_SECRET, "your-secret-key-change-in-production")
                or len(self.SECRET_KEY) < 32
            ):
                raise ValueError("SECRET_KEY must be set to a random value of at least 32 characters outside dev/test")
            if "*" in self.CORS_ORIGINS:
                raise ValueError("CORS_ORIGINS must not contain '*' outside dev/test")
        return self


settings = Settings()
