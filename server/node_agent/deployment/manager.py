from dataclasses import dataclass

from ..runtime.base import ModelRuntime


@dataclass
class DeploymentInfo:
    deployment_id: str
    model_source: str
    model_name: str
    runtime_name: str
    container_id: str
    endpoint_url: str
    status: str


class DeploymentManager:
    def __init__(self, runtime: ModelRuntime):
        self.runtime = runtime
        self._deployments: dict[str, DeploymentInfo] = {}

    async def deploy(
        self, deployment_id: str, model_source: str, model_name: str, runtime_name: str, config: dict
    ) -> DeploymentInfo:
        result = await self.runtime.deploy(deployment_id, model_source, config)
        if not result.success:
            raise Exception(f"Deployment failed: {result.error}")

        info = DeploymentInfo(
            deployment_id=deployment_id,
            model_source=model_source,
            model_name=model_name,
            runtime_name=runtime_name,
            container_id=result.container_id,
            endpoint_url=result.endpoint_url,
            status="running",
        )
        self._deployments[deployment_id] = info
        return info

    async def stop(self, deployment_id: str) -> bool:
        if deployment_id not in self._deployments:
            return False
        info = self._deployments[deployment_id]
        success = await self.runtime.stop(info.container_id)
        if success:
            info.status = "stopped"
            del self._deployments[deployment_id]
        return success

    async def restart(self, deployment_id: str) -> bool:
        if deployment_id not in self._deployments:
            return False
        info = self._deployments[deployment_id]
        success = await self.runtime.restart(info.container_id)
        if success:
            info.status = "running"
        return success

    async def get_status(self, deployment_id: str) -> DeploymentInfo | None:
        return self._deployments.get(deployment_id)

    def list_deployments(self) -> list[DeploymentInfo]:
        return list(self._deployments.values())
