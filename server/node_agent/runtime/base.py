from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class DeploymentResult:
    success: bool
    container_id: str
    endpoint_url: str
    error: str = None


@dataclass
class HealthCheckResult:
    status: str
    details: str = None


@dataclass
class RuntimeMetrics:
    cpu_usage: float
    memory_usage: float
    gpu_usage: float = 0.0


class ModelRuntime(ABC):
    @abstractmethod
    async def deploy(self, model_id: str, model_source: str, config: dict) -> DeploymentResult:
        pass

    @abstractmethod
    async def stop(self, container_id: str) -> bool:
        pass

    @abstractmethod
    async def restart(self, container_id: str) -> bool:
        pass

    @abstractmethod
    async def health_check(self, container_id: str) -> HealthCheckResult:
        pass

    @abstractmethod
    async def get_metrics(self, container_id: str) -> RuntimeMetrics:
        pass

    @abstractmethod
    async def get_logs(self, container_id: str, tail: int = 100) -> str:
        pass
