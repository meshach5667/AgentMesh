import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.model import Model
from app.models.node import Node
from app.models.transaction import Transaction, TransactionStatus, TransactionType
from app.models.usage import UsageRecord
from app.models.user import Customer, Provider
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
        started_at=datetime.utcnow(),
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
        workload.completed_at = datetime.utcnow()
        workload.tokens_in = _estimate_tokens(payload.input)
        workload.tokens_out = _estimate_tokens(result)
        await _settle_usage(db, workload, candidates[0], workload.tokens_in + workload.tokens_out)
    except httpx.TimeoutException:
        workload.status = WorkloadStatus.TIMEOUT
        workload.error_code = "NODE_TIMEOUT"
        workload.error_message = "Node execution timed out"
        workload.completed_at = datetime.utcnow()
    except Exception as exc:
        workload.status = WorkloadStatus.FAILED
        workload.error_code = "EXECUTION_FAILED"
        workload.error_message = str(exc)
        workload.completed_at = datetime.utcnow()
    await db.commit()
    await db.refresh(workload)
    return workload


async def _dispatch_to_node(node: Node, workload: Workload, model: Model) -> dict[str, Any]:
    endpoint = (node.public_key or "").rstrip("/")
    if not endpoint.startswith(("http://", "https://")):
        return {"text": workload.input_data.get("prompt", workload.input_data.get("messages", workload.input_data))}
    headers = {"Authorization": f"Bearer {node.api_key_hash}"}
    request = {
        "workload_id": str(workload.id),
        "model": model.name,
        "input": workload.input_data,
    }
    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(f"{endpoint}/api/v1/inference", json=request, headers=headers)
        response.raise_for_status()
        return response.json()


def _estimate_tokens(value: Any) -> int:
    return len(str(value).split())


def _calculate_cost(token_count: int) -> Decimal:
    return max(Decimal("0.001"), (Decimal(token_count) / Decimal("1000")) * Decimal("0.01"))


async def _settle_usage(db: AsyncSession, workload: Workload, node: Node, token_count: int) -> None:
    customer_result = await db.execute(select(Customer).where(Customer.id == workload.customer_id))
    customer = customer_result.scalars().first()
    if not customer:
        raise HTTPException(status_code=500, detail="Workload customer not found")
    wallet_result = await db.execute(select(Wallet).where(Wallet.user_id == customer.user_id).with_for_update())
    wallet = wallet_result.scalars().first()
    if not wallet:
        raise HTTPException(status_code=402, detail="Customer wallet not found")

    provider_result = await db.execute(
        select(Provider).join(Node, Node.owner_id == Provider.id).where(Node.id == node.id)
    )
    provider = provider_result.scalars().first()
    if not provider:
        raise HTTPException(status_code=500, detail="Node provider not found")

    cost = _calculate_cost(token_count)
    platform_fee = cost * Decimal("0.10")
    provider_amount = cost - platform_fee
    wallet.balance = Decimal(wallet.balance or 0) - cost
    provider.balance = Decimal(provider.balance or 0) + provider_amount
    usage = UsageRecord(
        workload_id=workload.id,
        node_id=node.id,
        gpu_seconds=0,
        cpu_seconds=0,
        total_cost=cost,
        period_start=workload.started_at,
        period_end=workload.completed_at,
    )
    db.add(usage)
    db.add(
        Transaction(
            from_wallet=wallet.id,
            amount=cost,
            type=TransactionType.COMPUTE_CHARGE,
            status=TransactionStatus.SETTLED,
            reference=f"workload:{workload.id}",
            description="Inference workload charge",
        )
    )
    db.add(
        Transaction(
            amount=provider_amount,
            type=TransactionType.PROVIDER_CREDIT,
            status=TransactionStatus.SETTLED,
            reference=f"workload:{workload.id}:provider",
            description="Provider earning",
        )
    )


async def get_workload(db: AsyncSession, workload_id: str, user_id: uuid.UUID) -> Workload:
    customer_result = await db.execute(select(Customer).where(Customer.user_id == user_id))
    customer = customer_result.scalars().first()
    if not customer:
        raise HTTPException(status_code=403, detail="Customer account required")
    result = await db.execute(select(Workload).where(Workload.id == workload_id, Workload.customer_id == customer.id))
    workload = result.scalars().first()
    if not workload:
        raise HTTPException(status_code=404, detail="Workload not found")
    return workload
