from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_roles
from app.models.user import UserRole
from app.schemas.model import ArtifactCreate, ArtifactOut, ArtifactUpdate, ModelCreate, ModelOut
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
    staff=Depends(require_roles(UserRole.operator, UserRole.admin)),
):
    # Catalog entries are created unapproved; approval is a separate, explicit operator decision.
    return await model_service.create_model(db, model, actor_id=staff.id)


@router.post("/{id}/approval", response_model=ModelOut)
async def set_model_approval(
    id: str,
    approved: bool = True,
    db: AsyncSession = Depends(get_db),
    staff=Depends(require_roles(UserRole.operator, UserRole.admin)),
):
    """Approve (or withdraw) a catalog entry for deployment. Approval does not guarantee a node can run it."""
    return await model_service.approve_model(db, id, approved, actor_id=staff.id)


@router.post("/{id}/artifacts", response_model=ArtifactOut, status_code=201)
async def add_artifact(
    id: str,
    artifact: ArtifactCreate,
    db: AsyncSession = Depends(get_db),
    staff=Depends(require_roles(UserRole.operator, UserRole.admin)),
):
    """Declare that a runtime can serve this model, from a pinned source. Validated like deployments are."""
    return await model_service.add_artifact(db, id, artifact, actor_id=staff.id)


@router.patch("/{id}/artifacts/{artifact_id}", response_model=ArtifactOut)
async def update_artifact(
    id: str,
    artifact_id: str,
    update: ArtifactUpdate,
    db: AsyncSession = Depends(get_db),
    staff=Depends(require_roles(UserRole.operator, UserRole.admin)),
):
    return await model_service.set_artifact_enabled(db, id, artifact_id, update.is_enabled, actor_id=staff.id)
