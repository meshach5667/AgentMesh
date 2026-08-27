import pytest
from unittest.mock import AsyncMock
from node_agent.deployment.manager import DeploymentManager
from node_agent.runtime.base import ModelRuntime, DeploymentResult

class DummyRuntime(ModelRuntime):
    async def deploy(self, model_id, model_source, config):
        return DeploymentResult(success=True, container_id="c1", endpoint_url="http://local")
    async def stop(self, container_id):
        return True
    async def restart(self, container_id):
        return True
    async def health_check(self, container_id):
        pass
    async def get_metrics(self, container_id):
        pass
    async def get_logs(self, container_id, tail=100):
        pass

@pytest.mark.asyncio
async def test_deployment_manager():
    runtime = DummyRuntime()
    manager = DeploymentManager(runtime)
    info = await manager.deploy("d1", "src", "name", "vllm", {})
    assert info.deployment_id == "d1"
    
    status = await manager.get_status("d1")
    assert status is not None
    assert status.status == "running"
    
    stopped = await manager.stop("d1")
    assert stopped is True
    assert len(manager.list_deployments()) == 0
