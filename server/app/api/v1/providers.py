"""Providers: their own profile and payment arrangement, and the offers customers browse.

Customers pay providers directly; AgentMesh only shows how. Offers and arrangements are visible to signed-in users.
"""

from typing import Literal

from fastapi import APIRouter, Depends

from app.core.database import Session, get_db
from app.core.dependencies import get_current_user, require_roles
from app.documents.user import UserRole
from app.schemas.credit import GatewayIn, GatewayOut
from app.schemas.provider import ProviderDetail, ProviderOffer, ProviderProfileIn, ProviderProfileOut
from app.services import credit_service, node_pricing_service, provider_service

router = APIRouter()


@router.get("/me", response_model=ProviderProfileOut)
async def my_profile(db: Session = Depends(get_db), current_user=Depends(require_roles(UserRole.provider))):
    provider = await node_pricing_service.provider_for(db, current_user)
    return provider_service.card(provider)


@router.put("/me", response_model=ProviderProfileOut)
async def update_my_profile(
    req: ProviderProfileIn, db: Session = Depends(get_db), current_user=Depends(require_roles(UserRole.provider))
):
    """Set the name customers see and how they pay you. AgentMesh shows it and processes no payments."""
    provider = await node_pricing_service.provider_for(db, current_user)
    provider = await provider_service.update_profile(db, provider, req.model_dump(mode="json"), current_user)
    return provider_service.card(provider)


@router.get("/me/gateways", response_model=list[GatewayOut])
async def my_gateways(db: Session = Depends(get_db), current_user=Depends(require_roles(UserRole.provider))):
    """Payment gateway accounts you connected (keys are never shown, only their last 4 characters)."""
    provider = await node_pricing_service.provider_for(db, current_user)
    return await credit_service.connected_gateways(db, provider.id)


@router.put("/me/gateways/{gateway}", response_model=GatewayOut)
async def connect_gateway(
    gateway: Literal["paystack", "flutterwave", "stripe"],
    body: GatewayIn,
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(UserRole.provider)),
):
    """Connect your own gateway account with its secret key, so customers' payments to you are verified
    automatically. The key is checked with the gateway, stored encrypted, and used only for your payments."""
    provider = await node_pricing_service.provider_for(db, current_user)
    return await credit_service.connect_gateway(db, provider, gateway, body.secret_key, current_user)


@router.delete("/me/gateways/{gateway}", status_code=204)
async def disconnect_gateway(
    gateway: Literal["paystack", "flutterwave", "stripe"],
    db: Session = Depends(get_db),
    current_user=Depends(require_roles(UserRole.provider)),
):
    provider = await node_pricing_service.provider_for(db, current_user)
    await credit_service.disconnect_gateway(db, provider, gateway, current_user)


@router.get("", response_model=list[ProviderOffer])
async def list_offers(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """Providers with machines that can take work now: capacity, runtimes, lowest prices and payment methods."""
    return await provider_service.offers(db)


@router.get("/{provider_id}", response_model=ProviderDetail)
async def provider_detail(provider_id: str, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    """One provider's offer and full payment arrangement."""
    provider = await provider_service.get_provider(db, provider_id)
    return await provider_service.detail(db, provider)
