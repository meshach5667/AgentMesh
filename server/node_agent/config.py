import os
from pathlib import Path
from urllib.parse import urlparse

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

WORKER_VERSION = "0.2.0"
PROTOCOL_VERSION = 1
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}


class WorkerSettings(BaseSettings):
    """Worker configuration. Environment variables use the AGENTMESH_ prefix, e.g. AGENTMESH_MAX_RAM_MB."""

    model_config = SettingsConfigDict(env_prefix="AGENTMESH_", env_file=None, extra="ignore")

    CONTROL_PLANE_URL: str = "http://localhost:8000"
    # Plain HTTP is only accepted for loopback hosts unless explicitly allowed (e.g. a private Compose network).
    ALLOW_INSECURE_CONTROL_PLANE: bool = False
    DATA_DIR: str = os.path.expanduser("~/.agentmesh/worker")
    MODE: str = "agent"  # "docker" (Docker worker) or "agent" (installable agent)
    RUNTIME_BACKEND: str = ""  # "docker" or "process"; defaults from MODE
    NODE_NAME: str = ""

    # Resources the provider allows AgentMesh to use. Unset values fall back to conservative defaults
    # (half the CPU and RAM, at most 20 GB of disk, no GPU) - never the whole machine.
    MAX_CPU_CORES: int | None = None
    MAX_RAM_MB: int | None = None
    MAX_DISK_MB: int | None = None
    ALLOW_GPU: bool = False
    MAX_VRAM_MB: int | None = None

    # Process backend (installable agent)
    OLLAMA_BINARY: str = "ollama"
    # Wrap runtime processes in a systemd user scope with MemoryMax/CPUQuota when available.
    PROCESS_CGROUP_LIMITS: bool = True

    # Docker backend. Pin the image by digest in production (AGENTMESH_OLLAMA_IMAGE=ollama/ollama@sha256:...).
    OLLAMA_IMAGE: str = "ollama/ollama:0.12.3"
    DOCKER_HOST: str = ""  # empty: docker-py defaults (DOCKER_HOST env or the local socket)
    WORKLOAD_NETWORK: str = ""  # set when the worker itself runs in a container on this network
    MODELS_VOLUME: str = "agentmesh-models"

    HEARTBEAT_INTERVAL_SECONDS: int = 15
    HEALTH_CHECK_INTERVAL_SECONDS: int = 30
    MAX_CONCURRENT_REQUESTS_PER_DEPLOYMENT: int = 4
    REQUEST_TIMEOUT_SECONDS: int = 600

    @model_validator(mode="after")
    def _check(self) -> "WorkerSettings":
        if self.MODE not in ("docker", "agent"):
            raise ValueError("AGENTMESH_MODE must be 'docker' or 'agent'")
        if not self.RUNTIME_BACKEND:
            self.RUNTIME_BACKEND = "docker" if self.MODE == "docker" else "process"
        if self.RUNTIME_BACKEND not in ("docker", "process"):
            raise ValueError("AGENTMESH_RUNTIME_BACKEND must be 'docker' or 'process'")
        url = urlparse(self.CONTROL_PLANE_URL)
        if url.scheme not in ("http", "https") or not url.hostname:
            raise ValueError("AGENTMESH_CONTROL_PLANE_URL must be an http(s) URL")
        if url.scheme == "http" and url.hostname not in LOCAL_HOSTS and not self.ALLOW_INSECURE_CONTROL_PLANE:
            raise ValueError(
                "Refusing plain HTTP to a non-local control plane. Use https:// or set "
                "AGENTMESH_ALLOW_INSECURE_CONTROL_PLANE=true for a trusted private network."
            )
        self.CONTROL_PLANE_URL = self.CONTROL_PLANE_URL.rstrip("/")
        return self

    @property
    def data_path(self) -> Path:
        return Path(self.DATA_DIR)


def load_settings(**overrides) -> WorkerSettings:
    return WorkerSettings(**overrides)
