from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.schemas.model import ModelCreate, ModelOut
from app.services import model_service

router = APIRouter()

@router.get("", response_model=list[ModelOut])
async def list_models(db: AsyncSession = Depends(get_db)):
    return await model_service.list_models(db)

@router.get("/{id}", response_model=ModelOut)
async def get_model(id: str, db: AsyncSession = Depends(get_db)):
    return await model_service.get_model(db, id)

@router.post("")
async def create_model(model: ModelCreate, db: AsyncSession = Depends(get_db)):
    return await model_service.create_model(db, model)
