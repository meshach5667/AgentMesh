import docker
import asyncio
from .base import ModelRuntime, DeploymentResult, HealthCheckResult, RuntimeMetrics

class OllamaRuntime(ModelRuntime):
    def __init__(self, docker_socket: str = None):
        if docker_socket:
            self.client = docker.DockerClient(base_url=docker_socket)
        else:
            self.client = docker.from_env()
            
    def _find_available_port(self):
        import socket
        for port in range(11434, 11500):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(('localhost', port)) != 0:
                    return port
        return 11434

    async def deploy(self, model_id: str, model_source: str, config: dict) -> DeploymentResult:
        try:
            port = self._find_available_port()
            container_name = f"agentmesh-ollama-{model_id}"
            
            device_requests = []
            if config.get("use_gpu", True):
                device_requests = [
                    docker.types.DeviceRequest(count=-1, capabilities=[['gpu']])
                ]
            
            container = self.client.containers.run(
                "ollama/ollama:latest",
                name=container_name,
                ports={'11434/tcp': port},
                device_requests=device_requests,
                detach=True
            )
            
            # Pull model
            exec_result = container.exec_run(f"ollama pull {model_source}")
            if exec_result.exit_code != 0:
                container.stop()
                container.remove()
                return DeploymentResult(success=False, container_id="", endpoint_url="", error=f"Failed to pull model: {exec_result.output.decode('utf-8')}")
                
            endpoint_url = f"http://localhost:{port}"
                    
            return DeploymentResult(
                success=True,
                container_id=container.id,
                endpoint_url=endpoint_url
            )
            
        except Exception as e:
            return DeploymentResult(success=False, container_id="", endpoint_url="", error=str(e))

    async def stop(self, container_id: str) -> bool:
        try:
            container = self.client.containers.get(container_id)
            container.stop()
            container.remove()
            return True
        except Exception:
            return False

    async def restart(self, container_id: str) -> bool:
        try:
            container = self.client.containers.get(container_id)
            container.restart()
            return True
        except Exception:
            return False

    async def health_check(self, container_id: str) -> HealthCheckResult:
        try:
            container = self.client.containers.get(container_id)
            if container.status == "running":
                return HealthCheckResult(status="healthy")
            return HealthCheckResult(status="unhealthy")
        except Exception as e:
            return HealthCheckResult(status="error", details=str(e))

    async def get_metrics(self, container_id: str) -> RuntimeMetrics:
        return RuntimeMetrics(0.0, 0.0)

    async def get_logs(self, container_id: str, tail: int = 100) -> str:
        try:
            container = self.client.containers.get(container_id)
            return container.logs(tail=tail).decode('utf-8')
        except Exception:
            return ""
