from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.config import settings
from app.core.database import Session, get_db
from app.core.dependencies import get_current_user
from app.core.ratelimit import limiters
from app.schemas.auth import AuthResponse, RefreshRequest, UserCreate, UserLogin, UserOut
from app.services import auth_service

router = APIRouter()


async def _throttle(request: Request, email: str | None) -> None:
    """Limit attempts per client address and per account (slows credential stuffing and guessing)."""
    client = request.client.host if request.client else "unknown"
    keys = [f"auth:ip:{client}"] + ([f"auth:email:{email.strip().lower()}"] if email else [])
    for key in keys:
        allowed, retry_after = await limiters.requests.allow(key, settings.AUTH_RATE_LIMIT_PER_MINUTE)
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail="Too many attempts. Try again shortly.",
                headers={"Retry-After": str(max(1, int(retry_after)))},
            )


@router.post("/register", response_model=AuthResponse)
async def register(user: UserCreate, request: Request, db: Session = Depends(get_db)):
    await _throttle(request, user.email)
    return await auth_service.register_user(db, user, request.headers.get("user-agent"))


@router.post("/login", response_model=AuthResponse)
async def login(user: UserLogin, request: Request, db: Session = Depends(get_db)):
    await _throttle(request, user.email)
    return await auth_service.login(db, user, request.headers.get("user-agent"))


@router.post("/refresh", response_model=AuthResponse)
async def refresh(body: RefreshRequest, request: Request, db: Session = Depends(get_db)):
    """Rotate a refresh token. The old one stops working; presenting it again ends the session."""
    await _throttle(request, None)
    return await auth_service.refresh(db, body.refresh_token)


@router.post("/logout", status_code=204)
async def logout(request: Request, db: Session = Depends(get_db), user=Depends(get_current_user)):
    await auth_service.revoke_session(db, request.state.auth_session, "logout", actor_id=user.id)
    await db.commit()


@router.post("/logout-all")
async def logout_all(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Sign out every session of this account, including this one (e.g. after a lost device)."""
    ended = await auth_service.revoke_all_sessions(db, user.id, "logout_all", actor_id=user.id)
    await db.commit()
    return {"sessions_ended": ended}


@router.get("/me", response_model=UserOut)
async def get_me(current_user=Depends(get_current_user)):
    return current_user
