import uuid

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.deployment import Deployment, DeploymentStatus
from app.models.user import Customer
from app.schemas.deployment import DeploymentCreate


async def create_deployment(db: AsyncSession, deployment_data: DeploymentCreate, user_id: uuid.UUID):
    result = await db.execute(select(Customer).filter(Customer.user_id == user_id))
    customer = result.scalars().first()
    if not customer:
        raise HTTPException(status_code=400, detail="User is not a customer")

    deployment = Deployment(
        customer_id=customer.id,
        model_id=deployment_data.model_id,
        config=deployment_data.config,
        status=DeploymentStatus.REQUESTED,
    )
    db.add(deployment)
    await db.commit()
    await db.refresh(deployment)
    return deployment


async def list_deployments(db: AsyncSession, user_id: uuid.UUID):
    result = await db.execute(select(Customer).filter(Customer.user_id == user_id))
    customer = result.scalars().first()
    if not customer:
        return []
    result = await db.execute(select(Deployment).filter(Deployment.customer_id == customer.id))
    return result.scalars().all()


async def get_deployment(db: AsyncSession, deployment_id: str):
    result = await db.execute(select(Deployment).filter(Deployment.id == deployment_id))
    deployment = result.scalars().first()
    if not deployment:
        raise HTTPException(status_code=404, detail="Deployment not found")
    return deployment


async def stop_deployment(db: AsyncSession, deployment_id: str):
    deployment = await get_deployment(db, deployment_id)
    deployment.status = DeploymentStatus.STOPPING
    await db.commit()
    return {"status": "stopping"}
