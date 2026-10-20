from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_roles
from app.models.user import UserRole
from app.schemas.model import ModelCreate, ModelOut
from app.services import model_service

router = APIRouter()


@router.get("", response_model=list[ModelOut])
async def list_models(db: AsyncSession = Depends(get_db)):
    return await model_service.list_models(db)


@router.get("/{id}", response_model=ModelOut)
async def get_model(id: str, db: AsyncSession = Depends(get_db)):
    return await model_service.get_model(db, id)


@router.post("", response_model=ModelOut)
async def create_model(
    model: ModelCreate,
    db: AsyncSession = Depends(get_db),
    _staff=Depends(require_roles(UserRole.operator, UserRole.admin)),
):
    # Catalog entries are created unapproved; approval is a separate, explicit operator decision.
    return await model_service.create_model(db, model)


@router.post("/{id}/approval", response_model=ModelOut)
async def set_model_approval(
    id: str,
    approved: bool = True,
    db: AsyncSession = Depends(get_db),
    _staff=Depends(require_roles(UserRole.operator, UserRole.admin)),
):
    """Approve (or withdraw) a catalog entry for deployment. Approval does not guarantee a node can run it."""
    return await model_service.approve_model(db, id, approved)
