"""Runtime adapter contract shared by all model-serving backends.

The worker only talks to runtimes through this interface, so adding llama.cpp or vLLM later means adding
an adapter, not changing the protocol, scheduler, or gateway.
"""

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field


class WorkloadError(Exception):
    """Runtime failure with a stable error code reported to the control plane."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class WorkloadSpec:
    deployment_id: str
    model_tag: str
    num_ctx: int
    cpu_cores: int
    ram_mb: int
    disk_mb: int
    vram_mb: int
    gpu: bool


@dataclass
class WorkloadHandle:
    """Everything needed to find a running workload again, persisted in the worker's state file."""

    deployment_id: str
    base_url: str  # private address of the runtime API, reachable only by the worker
    backend: str
    ref: dict = field(default_factory=dict)  # backend-specific: pid/port or container id


@dataclass
class RuntimeCapabilities:
    name: str
    version: str
    backend: str
    available: bool
    gpu: bool
    limits_enforced: bool  # True when CPU/memory limits are enforced by the OS (cgroups/containers)
    detail: str = ""


ProgressCallback = Callable[[str], Awaitable[None]]


class WorkloadRuntime(ABC):
    name: str
    backend: str

    @abstractmethod
    async def capabilities(self) -> RuntimeCapabilities: ...

    @abstractmethod
    async def start(self, spec: WorkloadSpec) -> WorkloadHandle:
        """Start an isolated, empty runtime instance for the workload and wait until its API answers."""

    @abstractmethod
    async def prepare_model(self, handle: WorkloadHandle, spec: WorkloadSpec, progress: ProgressCallback) -> None:
        """Download the model into the instance."""

    @abstractmethod
    async def verify_ready(self, handle: WorkloadHandle, spec: WorkloadSpec) -> str | None:
        """Prove the model can serve a request. Returns the model digest when the runtime reports one."""

    @abstractmethod
    async def health(self, handle: WorkloadHandle, spec: WorkloadSpec) -> bool: ...

    @abstractmethod
    async def remove(self, handle: WorkloadHandle) -> None:
        """Stop the instance and remove everything created for it except the shared model cache."""

    @abstractmethod
    async def is_alive(self, handle: WorkloadHandle) -> bool: ...
