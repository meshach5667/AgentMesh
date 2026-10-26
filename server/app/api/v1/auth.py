from fastapi import APIRouter, Depends, HTTPException, Request

from app.core.config import settings
from app.core.database import Session, get_db
from app.core.dependencies import get_session_user
from app.core.ratelimit import limiters
from app.schemas.auth import (
    AuthResponse,
    MeOut,
    MfaChallenge,
    MfaCode,
    MfaSetup,
    MfaVerify,
    RefreshRequest,
    UserCreate,
    UserLogin,
)
from app.services import auth_service, mfa_service

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


@router.post("/login", response_model=AuthResponse | MfaChallenge)
async def login(user: UserLogin, request: Request, db: Session = Depends(get_db)):
    await _throttle(request, user.email)
    return await auth_service.login(db, user, request.headers.get("user-agent"))


@router.post("/refresh", response_model=AuthResponse)
async def refresh(body: RefreshRequest, request: Request, db: Session = Depends(get_db)):
    """Rotate a refresh token. The old one stops working; presenting it again ends the session."""
    await _throttle(request, None)
    return await auth_service.refresh(db, body.refresh_token)


@router.post("/logout", status_code=204)
async def logout(request: Request, db: Session = Depends(get_db), user=Depends(get_session_user)):
    await auth_service.revoke_session(db, request.state.auth_session, "logout", actor_id=user.id)
    await db.commit()


@router.post("/logout-all")
async def logout_all(db: Session = Depends(get_db), user=Depends(get_session_user)):
    """Sign out every session of this account, including this one (e.g. after a lost device)."""
    ended = await auth_service.revoke_all_sessions(db, user.id, "logout_all", actor_id=user.id)
    await db.commit()
    return {"sessions_ended": ended}


@router.post("/mfa/verify", response_model=AuthResponse)
async def mfa_verify(body: MfaVerify, request: Request, db: Session = Depends(get_db)):
    """Second step of signing in to an account with two-factor authentication."""
    await _throttle(request, None)
    return await auth_service.login_with_second_factor(db, body.mfa_token, body.code, request.headers.get("user-agent"))


@router.post("/mfa/setup", response_model=MfaSetup)
async def mfa_setup(db: Session = Depends(get_db), user=Depends(get_session_user)):
    """Start turning on two-factor authentication: add the secret to an authenticator app, then confirm a code."""
    return await mfa_service.begin_setup(db, user)


@router.post("/mfa/enable", status_code=204)
async def mfa_enable(body: MfaCode, request: Request, db: Session = Depends(get_db), user=Depends(get_session_user)):
    await _throttle(request, user.email)
    await mfa_service.enable(db, user, request.state.auth_session, body.code)


@router.post("/mfa/disable", status_code=204)
async def mfa_disable(body: MfaCode, request: Request, db: Session = Depends(get_db), user=Depends(get_session_user)):
    await _throttle(request, user.email)
    await mfa_service.disable(db, user, body.code)


@router.get("/me", response_model=MeOut)
async def get_me(request: Request, current_user=Depends(get_session_user)):
    return MeOut.model_validate(current_user, from_attributes=True).model_copy(
        update={
            "mfa_required": mfa_service.mfa_required_for(current_user),
            "mfa_verified": request.state.auth_session.mfa_verified,
        }
    )
