import os

from pydantic_settings import BaseSettings


class NodeSettings(BaseSettings):
    CONTROL_PLANE_URL: str = "http://localhost:8000"
    NODE_AGENT_HOST: str = "0.0.0.0"
    NODE_AGENT_PORT: int = 8001
    HEARTBEAT_INTERVAL_SECONDS: int = 30
    METRICS_INTERVAL_SECONDS: int = 15
    USAGE_REPORT_INTERVAL_SECONDS: int = 60
    DATA_DIR: str = os.path.expanduser("~/.agentmesh/node")
    NODE_API_KEY: str = ""
    NODE_ID: str = ""
    LOG_LEVEL: str = "INFO"
    DOCKER_SOCKET: str = "npipe://./pipe/docker_engine" if os.name == "nt" else "unix:///var/run/docker.sock"
    DEFAULT_RUNTIME: str = "vllm"

    class Config:
        env_file = ".env"


settings = NodeSettings()
