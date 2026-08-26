from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.schemas.node import NodeCreate, NodeOut, NodeHardwareUpdate, NodePricingUpdate
from app.services import node_service
from app.core.dependencies import get_current_user

router = APIRouter()

@router.post("/register")
async def register_node(node: NodeCreate, db: AsyncSession = Depends(get_db), current_user = Depends(get_current_user)):
    return await node_service.register_node(db, node, current_user.id)

@router.get("", response_model=list[NodeOut])
async def list_nodes(db: AsyncSession = Depends(get_db), current_user = Depends(get_current_user)):
    return await node_service.list_nodes(db, current_user.id)

@router.get("/{id}")
async def get_node(id: str, db: AsyncSession = Depends(get_db)):
    return await node_service.get_node(db, id)

@router.post("/{id}/heartbeat")
async def heartbeat(id: str, db: AsyncSession = Depends(get_db)):
    return await node_service.process_heartbeat(db, id)
