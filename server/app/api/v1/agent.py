from fastapi import APIRouter
router = APIRouter()
@router.post("/deploy")
async def deploy_agent():
    return {"status": "ok"}
@router.get("/tasks")
async def list_tasks():
    return []
@router.get("/tasks/{id}")
async def get_task(id: str):
    return {}
