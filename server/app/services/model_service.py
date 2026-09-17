from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.models.model import Model
from app.schemas.model import ModelCreate


async def list_models(db: AsyncSession):
    result = await db.execute(select(Model).filter(Model.is_approved))
    return result.scalars().all()


async def get_model(db: AsyncSession, model_id: str):
    result = await db.execute(select(Model).filter(Model.id == model_id))
    model = result.scalars().first()
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    return model


async def create_model(db: AsyncSession, model_data: ModelCreate):
    model = Model(**model_data.dict())
    db.add(model)
    await db.commit()
    await db.refresh(model)
    return model
