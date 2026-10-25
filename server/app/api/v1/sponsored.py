"""Public sponsored-placement endpoints: what a slot shows, and impression and click counting."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, ConfigDict, Field

from app.core.database import Session, get_db
from app.core.ratelimit import limiters
from app.services import sponsorship_service

router = APIRouter()
VIEWS_PER_MINUTE = 120


class ImpressionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    placement: str = Field(max_length=40)
    token: str = Field(max_length=120)


async def _throttle(request: Request) -> None:
    client = request.client.host if request.client else "unknown"
    allowed, _ = await limiters.requests.allow(f"sponsored:{client}", VIEWS_PER_MINUTE)
    if not allowed:
        raise HTTPException(status_code=429, detail="Too many requests")


@router.get("")
async def sponsored(placement: str = Query(max_length=40), db: Session = Depends(get_db)):
    """Items for one slot (empty when advertising or the slot is off). Each item is labelled as sponsored by the
    dashboard and carries a signed token for counting its impression and click."""
    return await sponsorship_service.serve(db, placement)


@router.post("/{campaign_id}/impression")
async def impression(campaign_id: str, body: ImpressionIn, request: Request, db: Session = Depends(get_db)):
    await _throttle(request)
    counted = await sponsorship_service.record(db, campaign_id, body.placement, body.token, "impression")
    return {"counted": counted}


@router.get("/{campaign_id}/click")
async def click(
    campaign_id: str,
    request: Request,
    placement: str = Query(max_length=40),
    token: str = Query(max_length=120),
    db: Session = Depends(get_db),
):
    """Count the click and redirect to the campaign's own URL (never one taken from the request)."""
    await _throttle(request)
    target = await sponsorship_service.click_target(db, campaign_id, placement, token)
    return RedirectResponse(target, status_code=302, headers={"Referrer-Policy": "no-referrer"})
