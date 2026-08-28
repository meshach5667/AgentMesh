from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.security import create_access_token, get_password_hash, verify_password
from app.models.user import Customer, Provider, User
from app.schemas.auth import UserCreate, UserLogin


async def register_user(db: AsyncSession, user_data: UserCreate):
    result = await db.execute(select(User).filter(User.email == user_data.email))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(email=user_data.email, hashed_password=get_password_hash(user_data.password), role=user_data.role)
    db.add(user)
    await db.commit()
    await db.refresh(user)

    if user.role == "provider":
        provider = Provider(user_id=user.id)
        db.add(provider)
    elif user.role == "customer":
        customer = Customer(user_id=user.id)
        db.add(customer)

    await db.commit()
    access_token = create_access_token(subject=user.id)
    return {"access_token": access_token, "token_type": "bearer"}


async def login(db: AsyncSession, user_data: UserLogin):
    result = await db.execute(select(User).filter(User.email == user_data.email))
    user = result.scalars().first()
    if not user or not verify_password(user_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token = create_access_token(subject=user.id)
    return {"access_token": access_token, "token_type": "bearer"}
