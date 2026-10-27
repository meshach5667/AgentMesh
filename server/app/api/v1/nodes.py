from fastapi import APIRouter, Depends, Header, HTTPException

from app.core.config import settings
from app.core.database import Session, get_db
from app.core.dependencies import get_current_user, require_roles
from app.documents.user import UserRole
from app.schemas.billing import DefaultPricesIn, DefaultPricesOut, NodePricingOut, Prices
from app.schemas.node import EnrollmentTokenCreate, EnrollmentTokenOut, NodeCreate, NodeOut, NodeUpdate
from app.services import node_pricing_service, node_service, worker_service

router = APIRouter()


@router.post("/register")
async def register_node(
    node: NodeCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(UserRole.provider)),
):
    return await node_service.register_node(db, node, current_user.id)


@router.post("/enrollment-tokens", response_model=EnrollmentTokenOut, status_code=201)
async def create_enrollment_token(
    req: EnrollmentTokenCreate,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(UserRole.provider)),
):
    """Issue a single-use token (valid for ENROLLMENT_TOKEN_TTL_MINUTES) for enrolling a worker."""
    return await worker_service.create_enrollment_token(db, current_user.id, req.name, req.region)


@router.get("/pricing/default", response_model=DefaultPricesOut)
async def default_prices(db: Session = Depends(get_db), current_user=Depends(require_roles(UserRole.provider))):
    """The prices each machine you enroll starts with (null: the network prices until you set its own)."""
    provider = await node_pricing_service.provider_for(db, current_user)
    return {"currency": settings.BILLING_CURRENCY, "prices": provider.default_prices}


@router.put("/pricing/default", response_model=DefaultPricesOut)
async def set_default_prices(
    req: DefaultPricesIn, db: Session = Depends(get_db), current_user=Depends(require_roles(UserRole.provider))
):
    provider = await node_pricing_service.provider_for(db, current_user)
    prices = req.model_dump(exclude={"apply_to_existing"})
    updated = await node_pricing_service.set_provider_default(db, provider, prices, req.apply_to_existing, current_user)
    return {"currency": settings.BILLING_CURRENCY, "prices": prices, "updated_machines": updated}


@router.get("", response_model=list[NodeOut])
async def list_nodes(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return await node_service.list_nodes(db, current_user.id)


@router.get("/{id}", response_model=NodeOut)
async def get_node(id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return await node_service.get_node_for_user(db, id, current_user)


@router.patch("/{id}", response_model=NodeOut)
async def update_node(id: str, req: NodeUpdate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if req.accepting_workloads is None and req.accepts_community_models is None:
        raise HTTPException(status_code=422, detail="Nothing to update")
    node = None
    if req.accepting_workloads is not None:
        node = await node_service.set_accepting_workloads(db, id, current_user, req.accepting_workloads)
    if req.accepts_community_models is not None:
        node = await node_service.set_accepts_community_models(db, id, current_user, req.accepts_community_models)
    return node


@router.get("/{id}/pricing", response_model=NodePricingOut)
async def node_pricing(id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """What this machine charges, its price history, and the network prices for comparison."""
    node = await node_service.get_node_for_user(db, id, current_user)
    return await node_pricing_service.node_pricing(db, node)


@router.put("/{id}/pricing", response_model=NodePricingOut)
async def set_node_pricing(
    id: str, req: Prices, db: Session = Depends(get_db), current_user=Depends(require_roles(UserRole.provider))
):
    """Publish new prices for this machine, in force at once for new placements. Deployments already on it are
    never billed above the rates they were placed at, so a decrease reaches them at once and an increase does not."""
    node = await node_service.get_node_for_user(db, id, current_user)
    await node_pricing_service.set_node_price(db, node, req.model_dump(), current_user)
    return await node_pricing_service.node_pricing(db, node)


@router.post("/{id}/revoke", response_model=NodeOut)
async def revoke_node(id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    return await node_service.revoke_node(db, id, current_user)


@router.post("/{id}/heartbeat", deprecated=True)
async def heartbeat(id: str, authorization: str = Header(default=""), db: Session = Depends(get_db)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Node credentials required")
    node = await node_service.authenticate_node(db, id, authorization.removeprefix("Bearer "))
    return await node_service.process_heartbeat(db, node)
