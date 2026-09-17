from fastapi import APIRouter, Depends, HTTPException, Security
from fastapi.security.api_key import APIKeyHeader
from pydantic import BaseModel

from ..hardware.discovery import discover_all
from ..metrics.collector import MetricsCollector

router = APIRouter()
api_key_header = APIKeyHeader(name="Authorization", auto_error=True)

# These will be injected from main.py
deployment_manager = None
metrics_collector = MetricsCollector()
settings = None


async def verify_api_key(api_key: str = Security(api_key_header)):
    token = api_key.replace("Bearer ", "") if api_key.startswith("Bearer ") else api_key
    if not settings or token != settings.NODE_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    return token


class DeployRequest(BaseModel):
    deployment_id: str
    model_id: str
    model_source: str
    model_name: str
    runtime: str
    config: dict = {}


class InferenceRequest(BaseModel):
    workload_id: str
    model: str
    input: dict


@router.get("/status")
async def get_status(api_key: str = Depends(verify_api_key)):
    deployments = deployment_manager.list_deployments() if deployment_manager else []
    return {"status": "online", "active_deployments": len(deployments)}


@router.get("/hardware")
async def get_hardware(api_key: str = Depends(verify_api_key)):
    return discover_all()


@router.get("/metrics")
async def get_metrics(api_key: str = Depends(verify_api_key)):
    return metrics_collector.collect_metrics()


@router.post("/deploy")
async def deploy_model(req: DeployRequest, api_key: str = Depends(verify_api_key)):
    if not deployment_manager:
        raise HTTPException(status_code=500, detail="Deployment manager not initialized")
    try:
        info = await deployment_manager.deploy(
            deployment_id=req.deployment_id,
            model_source=req.model_source,
            model_name=req.model_name,
            runtime_name=req.runtime,
            config=req.config,
        )
        return info
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/inference")
async def run_inference(req: InferenceRequest, api_key: str = Depends(verify_api_key)):
    """Run the MVP's controlled inference contract without arbitrary code execution."""
    if "messages" in req.input:
        messages = req.input["messages"]
        prompt = messages[-1].get("content", "") if messages else ""
    else:
        prompt = req.input.get("prompt", "")
    return {
        "workload_id": req.workload_id,
        "model": req.model,
        "text": prompt,
        "runtime": "controlled-mvp",
    }


@router.get("/deployments/{id}")
async def get_deployment_status(id: str, api_key: str = Depends(verify_api_key)):
    if not deployment_manager:
        raise HTTPException(status_code=500, detail="Not initialized")
    info = await deployment_manager.get_status(id)
    if not info:
        raise HTTPException(status_code=404, detail="Not found")
    return info


@router.post("/deployments/{id}/restart")
async def restart_deployment(id: str, api_key: str = Depends(verify_api_key)):
    if not deployment_manager:
        raise HTTPException(status_code=500, detail="Not initialized")
    success = await deployment_manager.restart(id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to restart")
    return {"status": "restarted"}


@router.post("/deployments/{id}/stop")
async def stop_deployment(id: str, api_key: str = Depends(verify_api_key)):
    if not deployment_manager:
        raise HTTPException(status_code=500, detail="Not initialized")
    success = await deployment_manager.stop(id)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to stop")
    return {"status": "stopped"}
