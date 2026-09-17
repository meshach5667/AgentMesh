from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.schemas.workload import InferenceRequest, WorkloadOut
from app.services import workload_service

router = APIRouter()


@router.post("/inference", response_model=WorkloadOut)
async def submit_inference(
    payload: InferenceRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    workload = await workload_service.create_inference(db, current_user.id, payload)
    return WorkloadOut.from_workload(workload)


@router.get("/workloads/{workload_id}", response_model=WorkloadOut)
async def get_workload(
    workload_id: str,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    workload = await workload_service.get_workload(db, workload_id, current_user.id)
    return WorkloadOut.from_workload(workload)
