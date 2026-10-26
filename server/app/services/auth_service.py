from fastapi import HTTPException

from app.core.database import Session
from app.core.security import (
    burn_password_check,
    create_access_token,
    get_password_hash,
    password_needs_rehash,
    verify_password,
)
from app.documents.user import Customer, Provider, User, UserRole
from app.schemas.auth import UserCreate, UserLogin
from app.services import audit_service


async def register_user(db: Session, user_data: UserCreate):
    if await db.find_one(User, {"email": user_data.email}):
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(email=user_data.email, hashed_password=get_password_hash(user_data.password), role=user_data.role.value)
    db.add(user)
    await db.flush()  # assign user.id without committing, so user + profile are created atomically

    if user.role == UserRole.provider.value:
        db.add(Provider(user_id=user.id))
    elif user.role == UserRole.customer.value:
        db.add(Customer(user_id=user.id))
    audit_service.record(
        db,
        actor_id=user.id,
        action="user.registered",
        resource_type="user",
        resource_id=user.id,
        details={"role": user.role},
    )
    await db.commit()
    await db.refresh(user)
    access_token = create_access_token(subject=user.id)
    return {"access_token": access_token, "token_type": "bearer", "user": user}


async def login(db: Session, user_data: UserLogin):
    user = await db.find_one(User, {"email": user_data.email})
    if user is None:
        burn_password_check(user_data.password)
    if not user or not verify_password(user_data.password, user.hashed_password):
        audit_service.record(
            db,
            actor_id=user.id if user else None,
            action="auth.login_failed",
            resource_type="user",
            resource_id=user.id if user else None,
            details={"email": user_data.email},
        )
        await db.commit()
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account disabled")
    if password_needs_rehash(user.hashed_password):
        user.hashed_password = get_password_hash(user_data.password)
    audit_service.record(db, actor_id=user.id, action="auth.login", resource_type="user", resource_id=user.id)
    await db.commit()

    access_token = create_access_token(subject=user.id)
    return {"access_token": access_token, "token_type": "bearer", "user": user}
