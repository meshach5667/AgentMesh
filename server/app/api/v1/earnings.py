from fastapi import APIRouter
router = APIRouter()
@router.get("")
async def get_earnings():
    return {"total": 0}
@router.get("/history")
async def get_history():
    return []
