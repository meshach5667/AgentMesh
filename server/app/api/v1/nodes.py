from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.schemas.node import NodeCreate, NodeOut
from app.services import node_service

router = APIRouter()


@router.post("/register")
async def register_node(node: NodeCreate, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    return await node_service.register_node(db, node, current_user.id)


@router.get("", response_model=list[NodeOut])
async def list_nodes(db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    return await node_service.list_nodes(db, current_user.id)


@router.get("/{id}")
async def get_node(id: str, db: AsyncSession = Depends(get_db)):
    return await node_service.get_node(db, id)


@router.post("/{id}/heartbeat")
async def heartbeat(id: str, authorization: str = Header(default=""), db: AsyncSession = Depends(get_db)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Node credentials required")
    await node_service.authenticate_node(db, id, authorization.removeprefix("Bearer "))
    return await node_service.process_heartbeat(db, id)
