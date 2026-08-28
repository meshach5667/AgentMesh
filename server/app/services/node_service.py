import datetime
import uuid

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.node import Node, NodeStatus
from app.models.user import Provider
from app.schemas.node import NodeCreate


async def register_node(db: AsyncSession, node_data: NodeCreate, user_id: uuid.UUID):
    result = await db.execute(select(Provider).filter(Provider.user_id == user_id))
    provider = result.scalars().first()
    if not provider:
        raise HTTPException(status_code=400, detail="User is not a provider")

    api_key = str(uuid.uuid4())
    node = Node(
        owner_id=provider.id,
        name=node_data.name,
        public_key=node_data.public_key,
        region=node_data.region,
        api_key_hash=api_key,
    )
    db.add(node)
    await db.commit()
    await db.refresh(node)
    return {"id": node.id, "api_key": api_key, "status": node.status}


async def list_nodes(db: AsyncSession, user_id: uuid.UUID):
    result = await db.execute(select(Provider).filter(Provider.user_id == user_id))
    provider = result.scalars().first()
    if not provider:
        return []
    result = await db.execute(select(Node).filter(Node.owner_id == provider.id))
    return result.scalars().all()


async def get_node(db: AsyncSession, node_id: str):
    result = await db.execute(select(Node).filter(Node.id == node_id))
    node = result.scalars().first()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    return node


async def process_heartbeat(db: AsyncSession, node_id: str):
    node = await get_node(db, node_id)
    node.last_heartbeat = datetime.datetime.utcnow()
    node.status = NodeStatus.ONLINE
    await db.commit()
    return {"status": "ok"}
