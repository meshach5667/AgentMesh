import uuid
from decimal import Decimal
from typing import Any

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ids import parse_uuid
from app.core.timeutil import utcnow
from app.models.model import Model
from app.models.node import Node
from app.models.user import Customer
from app.models.wallet import Wallet
from app.models.workload import Workload, WorkloadStatus
from app.services.scheduler_service import find_capable_nodes, rank_nodes


async def create_inference(db: AsyncSession, user_id: uuid.UUID, payload: Any) -> Workload:
    customer_result = await db.execute(select(Customer).where(Customer.user_id == user_id))
    customer = customer_result.scalars().first()
    if not customer:
        raise HTTPException(status_code=403, detail="Customer account required")

    model_query = select(Model).where(Model.is_approved.is_(True))
    try:
        model_query = model_query.where(Model.id == uuid.UUID(payload.model))
    except ValueError:
        model_query = model_query.where(Model.name == payload.model)
    model_result = await db.execute(model_query)
    model = model_result.scalars().first()
    if not model:
        raise HTTPException(status_code=404, detail="Approved model not found")

    requirements = dict(payload.requirements)
    if model.minimum_vram is not None:
        requirements.setdefault("min_vram_gb", model.minimum_vram)
    requirements.setdefault("gpu_required", model.minimum_vram is not None)

    candidates = rank_nodes(await find_capable_nodes(db, requirements))
    if not candidates:
        raise HTTPException(status_code=503, detail="No eligible compute nodes available")

    wallet_result = await db.execute(select(Wallet).where(Wallet.user_id == user_id).with_for_update())
    wallet = wallet_result.scalars().first()
    estimated_cost = _calculate_cost(_estimate_tokens(payload.input))
    if not wallet or Decimal(wallet.balance or 0) < estimated_cost:
        raise HTTPException(status_code=402, detail="Insufficient account balance")

    workload = Workload(
        customer_id=customer.id,
        model_id=model.id,
        node_id=candidates[0].id,
        status=WorkloadStatus.ASSIGNED,
        input_data=payload.input,
        started_at=utcnow(),
    )
    db.add(workload)
    await db.commit()
    await db.refresh(workload)

    try:
        workload.status = WorkloadStatus.RUNNING
        await db.commit()
        result = await _dispatch_to_node(candidates[0], workload, model)
        workload.result_data = result
        workload.status = WorkloadStatus.COMPLETED
        workload.completed_at = utcnow()
        workload.tokens_in = _estimate_tokens(payload.input)
        workload.tokens_out = _estimate_tokens(result)
        # Legacy one-shot workloads are not billed; billed inference goes through deployments.
    except NoInferenceEndpointError as exc:
        workload.status = WorkloadStatus.FAILED
        workload.error_code = "NO_INFERENCE_ENDPOINT"
        workload.error_message = str(exc)
        workload.completed_at = utcnow()
    except httpx.TimeoutException:
        workload.status = WorkloadStatus.TIMEOUT
        workload.error_code = "NODE_TIMEOUT"
        workload.error_message = "Node execution timed out"
        workload.completed_at = utcnow()
    except Exception:
        workload.status = WorkloadStatus.FAILED
        workload.error_code = "EXECUTION_FAILED"
        workload.error_message = "Inference execution failed"
        workload.completed_at = utcnow()
    await db.commit()
    await db.refresh(workload)
    return workload


class NoInferenceEndpointError(Exception):
    """Raised when no real model-serving endpoint exists for the selected node."""


async def _dispatch_to_node(node: Node, workload: Workload, model: Model) -> dict[str, Any]:
    # Nodes do not yet expose a verified, gateway-routed inference endpoint (see docs/IMPLEMENTATION_PLAN.md,
    # Phase 2). Fail explicitly instead of fabricating a response: earlier code echoed the prompt back and
    # billed the customer for it.
    raise NoInferenceEndpointError("No ready model deployment is available on the selected node")


def _estimate_tokens(value: Any) -> int:
    return len(str(value).split())


def _calculate_cost(token_count: int) -> Decimal:
    return max(Decimal("0.001"), (Decimal(token_count) / Decimal("1000")) * Decimal("0.01"))


async def get_workload(db: AsyncSession, workload_id: str, user_id: uuid.UUID) -> Workload:
    customer_result = await db.execute(select(Customer).where(Customer.user_id == user_id))
    customer = customer_result.scalars().first()
    if not customer:
        raise HTTPException(status_code=403, detail="Customer account required")
    result = await db.execute(
        select(Workload).where(Workload.id == parse_uuid(workload_id, "Workload"), Workload.customer_id == customer.id)
    )
    workload = result.scalars().first()
    if not workload:
        raise HTTPException(status_code=404, detail="Workload not found")
    return workload
