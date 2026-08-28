from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.schemas.deployment import DeploymentCreate, DeploymentOut
from app.services import deployment_service

router = APIRouter()


@router.post("", response_model=DeploymentOut)
async def create_deployment(
    deployment: DeploymentCreate, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)
):
    return await deployment_service.create_deployment(db, deployment, current_user.id)


@router.get("", response_model=list[DeploymentOut])
async def list_deployments(db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    return await deployment_service.list_deployments(db, current_user.id)


@router.get("/{id}", response_model=DeploymentOut)
async def get_deployment(id: str, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    return await deployment_service.get_deployment(db, id)


@router.post("/{id}/stop")
async def stop_deployment(id: str, db: AsyncSession = Depends(get_db), current_user=Depends(get_current_user)):
    return await deployment_service.stop_deployment(db, id)
