import docker
import asyncio
import httpx
from .base import ModelRuntime, DeploymentResult, HealthCheckResult, RuntimeMetrics

class VLLMRuntime(ModelRuntime):
    def __init__(self, docker_socket: str = None):
        if docker_socket:
            self.client = docker.DockerClient(base_url=docker_socket)
        else:
            self.client = docker.from_env()
            
    def _find_available_port(self):
        import socket
        for port in range(8100, 8200):
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                if s.connect_ex(('localhost', port)) != 0:
                    return port
        return 8100

    async def deploy(self, model_id: str, model_source: str, config: dict) -> DeploymentResult:
        try:
            port = self._find_available_port()
            container_name = f"agentmesh-{model_id}"
            
            # Simple device request for GPU if needed
            device_requests = []
            if config.get("use_gpu", True):
                device_requests = [
                    docker.types.DeviceRequest(count=-1, capabilities=[['gpu']])
                ]
            
            container = self.client.containers.run(
                "vllm/vllm-openai:latest",
                command=f"--model {model_source} --gpu-memory-utilization 0.9",
                name=container_name,
                ports={'8000/tcp': port},
                device_requests=device_requests,
                detach=True
            )
            
            endpoint_url = f"http://localhost:{port}"
            
            # Wait for health
            for _ in range(60):
                await asyncio.sleep(2)
                try:
                    async with httpx.AsyncClient() as c:
                        resp = await c.get(f"{endpoint_url}/health")
                        if resp.status_code == 200:
                            break
                except:
                    pass
                    
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
        except docker.errors.NotFound:
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
            return HealthCheckResult(status="unhealthy", details=f"Status: {container.status}")
        except Exception as e:
            return HealthCheckResult(status="error", details=str(e))

    async def get_metrics(self, container_id: str) -> RuntimeMetrics:
        try:
            container = self.client.containers.get(container_id)
            stats = container.stats(stream=False)
            
            cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - stats['precpu_stats']['cpu_usage']['total_usage']
            system_delta = stats['cpu_stats']['system_cpu_usage'] - stats['precpu_stats']['system_cpu_usage']
            cpu_usage = 0.0
            if system_delta > 0.0 and cpu_delta > 0.0:
                cpu_usage = (cpu_delta / system_delta) * len(stats['cpu_stats']['cpu_usage']['percpu_usage']) * 100.0
                
            mem_usage = stats['memory_stats'].get('usage', 0)
            
            return RuntimeMetrics(
                cpu_usage=cpu_usage,
                memory_usage=mem_usage / (1024**2) # MB
            )
        except Exception:
            return RuntimeMetrics(0.0, 0.0)

    async def get_logs(self, container_id: str, tail: int = 100) -> str:
        try:
            container = self.client.containers.get(container_id)
            return container.logs(tail=tail).decode('utf-8')
        except Exception:
            return ""
