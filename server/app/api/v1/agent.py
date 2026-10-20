from fastapi import APIRouter, HTTPException

router = APIRouter()

_NOT_IMPLEMENTED = "AI agent workloads are not implemented yet"


@router.post("/deploy")
async def deploy_agent():
    raise HTTPException(status_code=501, detail=_NOT_IMPLEMENTED)


@router.get("/tasks")
async def list_tasks():
    raise HTTPException(status_code=501, detail=_NOT_IMPLEMENTED)


@router.get("/tasks/{id}")
async def get_task(id: str):
    raise HTTPException(status_code=501, detail=_NOT_IMPLEMENTED)
