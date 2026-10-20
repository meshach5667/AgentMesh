"""Worker protocol v1 endpoints. Used identically by the Docker worker and the installable agent.

All calls are outbound from the worker. Authentication: ``Authorization: Bearer <node credential>`` plus
``X-AgentMesh-Node-Id`` and ``X-AgentMesh-Protocol`` headers (enrollment uses a one-time token instead).
"""

import logging

from fastapi import APIRouter, Depends, Header, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db, session_scope
from app.models.node import Node
from app.schemas.worker import (
    CommandAck,
    DeploymentStatusReport,
    EnrollRequest,
    EnrollResponse,
    HeartbeatRequest,
    HeartbeatResponse,
    PollRequest,
    PollResponse,
)
from app.services import worker_service
from app.services.tunnel import WorkerConnection, broker

logger = logging.getLogger(__name__)
router = APIRouter()


async def current_node(
    db: AsyncSession = Depends(get_db),
    authorization: str = Header(default=""),
    x_agentmesh_node_id: str | None = Header(default=None),
    x_agentmesh_protocol: str | None = Header(default=None),
) -> Node:
    credential = authorization[7:] if authorization.lower().startswith("bearer ") else None
    return await worker_service.authenticate_worker(db, x_agentmesh_node_id, credential, x_agentmesh_protocol or "1")


@router.post("/enroll", response_model=EnrollResponse)
async def enroll(req: EnrollRequest, db: AsyncSession = Depends(get_db)):
    return await worker_service.enroll(db, req)


@router.post("/heartbeat", response_model=HeartbeatResponse)
async def heartbeat(req: HeartbeatRequest, node: Node = Depends(current_node), db: AsyncSession = Depends(get_db)):
    return await worker_service.heartbeat(db, node, req)


@router.post("/disconnect")
async def disconnect(node: Node = Depends(current_node), db: AsyncSession = Depends(get_db)):
    await worker_service.disconnect(db, node)
    return {"ok": True}


@router.post("/commands/poll", response_model=PollResponse)
async def poll(req: PollRequest, node: Node = Depends(current_node), db: AsyncSession = Depends(get_db)):
    return {"commands": await worker_service.poll_commands(db, node, req.max_commands, req.wait_seconds)}


@router.post("/commands/{command_id}/ack")
async def ack(command_id: str, req: CommandAck, node: Node = Depends(current_node), db: AsyncSession = Depends(get_db)):
    await worker_service.ack_command(db, node, command_id, req.status, req.error)
    return {"ok": True}


@router.post("/deployments/{deployment_id}/status")
async def deployment_status(
    deployment_id: str,
    report: DeploymentStatusReport,
    node: Node = Depends(current_node),
    db: AsyncSession = Depends(get_db),
):
    return await worker_service.report_deployment_status(db, node, deployment_id, report)


@router.websocket("/tunnel")
async def tunnel(websocket: WebSocket):
    headers = websocket.headers
    auth = headers.get("authorization", "")
    credential = auth[7:] if auth.lower().startswith("bearer ") else None
    try:
        async with session_scope() as db:
            node = await worker_service.authenticate_worker(
                db, headers.get("x-agentmesh-node-id"), credential, headers.get("x-agentmesh-protocol") or "1"
            )
            node_id = node.id
    except Exception:  # noqa: BLE001
        await websocket.close(code=4401)
        return
    await websocket.accept()
    conn = WorkerConnection(node_id=node_id, send_json=websocket.send_json, close=websocket.close)
    await broker.register(conn)
    logger.info("Worker tunnel connected for node %s", node_id)
    try:
        await broker.handle_messages(conn, websocket.receive_text)
    except WebSocketDisconnect:
        pass
    finally:
        broker.unregister(conn)
        logger.info("Worker tunnel closed for node %s", node_id)
