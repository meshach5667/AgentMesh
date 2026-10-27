from fastapi import APIRouter, Depends

from app.core.database import Session, get_db, retry_transient
from app.core.dependencies import get_current_user, require_roles
from app.documents.user import UserRole
from app.schemas.billing import DeploymentPricingOut, QuoteOut
from app.schemas.deployment import DeploymentCreate, DeploymentEventOut, DeploymentOut
from app.services import deployment_service

router = APIRouter()


@router.post("", response_model=DeploymentOut, status_code=201)
async def create_deployment(
    deployment: DeploymentCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(UserRole.customer)),
):
    return await retry_transient(db, lambda: deployment_service.create_deployment(db, deployment, current_user.id))


@router.post("/quote", response_model=QuoteOut)
async def quote_deployment(
    deployment: DeploymentCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(UserRole.customer)),
):
    """Price a deployment before creating it: the machine placement would pick now, per runtime, and the price
    limits applied. Reserves nothing."""
    return await deployment_service.quote(db, deployment, current_user.id)


@router.get("", response_model=list[DeploymentOut])
async def list_deployments(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return await deployment_service.list_deployments(db, current_user.id)


@router.get("/{id}", response_model=DeploymentOut)
async def get_deployment(id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return await deployment_service.get_deployment_for_user(db, id, current_user)


@router.get("/{id}/pricing", response_model=DeploymentPricingOut)
async def deployment_pricing(id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """The rates this deployment is billed at now, and the most it can be billed on its current machine."""
    return await deployment_service.pricing_for(db, id, current_user)


@router.post("/{id}/stop")
async def stop_deployment(id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return await deployment_service.stop_deployment(db, id, current_user)


@router.post("/{id}/restart")
async def restart_deployment(id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Restart on the same node from the cached model. The endpoint and API keys are unchanged."""
    return await deployment_service.restart_deployment(db, id, current_user)


@router.delete("/{id}")
async def delete_deployment(id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return await deployment_service.delete_deployment(db, id, current_user)


@router.get("/{id}/events", response_model=list[DeploymentEventOut])
async def deployment_events(id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return await deployment_service.list_events(db, id, current_user)
