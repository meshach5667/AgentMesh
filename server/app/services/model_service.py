from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from app.core.ids import parse_uuid
from app.models.model import Model
from app.schemas.model import ModelCreate


async def list_models(db: AsyncSession):
    result = await db.execute(select(Model).filter(Model.is_approved))
    return result.scalars().all()


async def get_model(db: AsyncSession, model_id: str):
    result = await db.execute(select(Model).filter(Model.id == parse_uuid(model_id, "Model")))
    model = result.scalars().first()
    if not model or not model.is_approved:
        raise HTTPException(status_code=404, detail="Model not found")
    return model


async def create_model(db: AsyncSession, model_data: ModelCreate):
    model = Model(**model_data.model_dump(), is_approved=False)
    db.add(model)
    await db.commit()
    await db.refresh(model)
    return model


async def approve_model(db: AsyncSession, model_id: str, approved: bool):
    model = await db.get(Model, parse_uuid(model_id, "Model"))
    if not model:
        raise HTTPException(status_code=404, detail="Model not found")
    model.is_approved = approved
    await db.commit()
    await db.refresh(model)
    return model
