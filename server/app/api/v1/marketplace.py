from fastapi import APIRouter
router = APIRouter()
@router.get("/nodes")
async def search_nodes():
    return []
@router.get("/pricing")
async def get_pricing():
    return {}
