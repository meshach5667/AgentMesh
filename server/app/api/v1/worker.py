"""Worker protocol v1 endpoints. Used identically by the Docker worker and the installable agent.

All calls are outbound from the worker. Authentication: ``Authorization: Bearer <node credential>`` plus
``X-AgentMesh-Node-Id`` and ``X-AgentMesh-Protocol`` headers (enrollment uses a one-time token instead).
"""

import asyncio
import contextlib
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse

from app.core import security_events
from app.core.config import settings
from app.core.database import Session, get_db, retry_transient, session_scope
from app.core.security import hash_secret
from app.documents.node import Node
from app.schemas.worker import (
    ChallengeResponse,
    CommandAck,
    DeploymentStatusReport,
    EnrollRequest,
    EnrollResponse,
    HeartbeatRequest,
    HeartbeatResponse,
    PollRequest,
    PollResponse,
    SessionRequest,
    SessionResponse,
)
from app.services import release_service, worker_service
from app.services.tunnel import WorkerConnection, broker

logger = logging.getLogger(__name__)
router = APIRouter()


async def current_node(
    db: Session = Depends(get_db),
    authorization: str = Header(default=""),
    x_agentmesh_node_id: str | None = Header(default=None),
    x_agentmesh_protocol: str | None = Header(default=None),
) -> Node:
    credential = authorization[7:] if authorization.lower().startswith("bearer ") else None
    return await worker_service.authenticate_worker(db, x_agentmesh_node_id, credential, x_agentmesh_protocol or "1")


async def _reload(db: Session, node: Node) -> Node:
    fresh = await db.get(Node, node.id)
    if fresh is None:
        raise HTTPException(status_code=401, detail="Invalid node credentials")
    return fresh


@router.post("/enroll", response_model=EnrollResponse)
async def enroll(req: EnrollRequest, db: Session = Depends(get_db)):
    return await worker_service.enroll(db, req)


async def enrolled_node(
    db: Session = Depends(get_db),
    authorization: str = Header(default=""),
    x_agentmesh_node_id: str | None = Header(default=None),
    x_agentmesh_protocol: str | None = Header(default=None),
) -> Node:
    """The long-lived enrollment credential itself (never a session token): needed, with a signature by the node
    key, to obtain a session."""
    credential = authorization[7:] if authorization.lower().startswith("bearer ") else None
    return await worker_service.authenticate_worker(
        db, x_agentmesh_node_id, credential, x_agentmesh_protocol or "1", enrollment_credential=True
    )


@router.post("/session/challenge", response_model=ChallengeResponse)
async def session_challenge(node: Node = Depends(enrolled_node), db: Session = Depends(get_db)):
    """A single-use challenge (60 s) for the worker to sign with its node key."""
    return await worker_service.issue_challenge(db, node)


@router.post("/session", response_model=SessionResponse)
async def session(req: SessionRequest, node: Node = Depends(enrolled_node), db: Session = Depends(get_db)):
    """Exchange a signed challenge for a short-lived session token (proof of possession of the node key)."""
    return await worker_service.create_session(db, node, req.challenge, req.signature)


@router.get("/releases/latest")
async def latest_release(node: Node = Depends(current_node)):
    release = release_service.latest()
    if release is None:
        raise HTTPException(status_code=404, detail="No worker release published")
    return release


@router.get("/releases/files/{name}")
async def release_file(name: str, node: Node = Depends(current_node)):
    path = release_service.wheel_path(name)
    if path is None:
        raise HTTPException(status_code=404, detail="Release file not found")
    return FileResponse(path, media_type="application/octet-stream", filename=name)


@router.get("/whoami")
async def whoami(node: Node = Depends(current_node)):
    """Read-only credential check used by `agentmesh-worker doctor`."""
    return {
        "node_id": str(node.id),
        "name": node.name,
        "status": node.status,
        "accepting_workloads": node.accepting_workloads,
        "worker_available": node.worker_available,
    }


@router.post("/heartbeat", response_model=HeartbeatResponse)
async def heartbeat(req: HeartbeatRequest, node: Node = Depends(current_node), db: Session = Depends(get_db)):
    async def attempt():
        # Reloaded on each attempt: the rollback before a retry forgets the node loaded for authentication.
        return await worker_service.heartbeat(db, await _reload(db, node), req)

    return await retry_transient(db, attempt)


@router.post("/disconnect")
async def disconnect(node: Node = Depends(current_node), db: Session = Depends(get_db)):
    await worker_service.disconnect(db, node)
    return {"ok": True}


@router.post("/commands/poll", response_model=PollResponse)
async def poll(req: PollRequest, node: Node = Depends(current_node), db: Session = Depends(get_db)):
    return {"commands": await worker_service.poll_commands(db, node, req.max_commands, req.wait_seconds)}


@router.post("/commands/{command_id}/ack")
async def ack(command_id: str, req: CommandAck, node: Node = Depends(current_node), db: Session = Depends(get_db)):
    async def attempt():
        await worker_service.ack_command(db, await _reload(db, node), command_id, req.status, req.error, req.nonce)

    await retry_transient(db, attempt)
    return {"ok": True}


@router.post("/deployments/{deployment_id}/status")
async def deployment_status(
    deployment_id: str,
    report: DeploymentStatusReport,
    node: Node = Depends(current_node),
    db: Session = Depends(get_db),
):
    async def attempt():
        return await worker_service.report_deployment_status(db, await _reload(db, node), deployment_id, report)

    return await retry_transient(db, attempt)


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
            node_id, credential_hash = node.id, hash_secret(credential or "")
    except Exception:  # noqa: BLE001
        await websocket.close(code=4401)
        return
    await websocket.accept()
    conn = WorkerConnection(node_id=node_id, send_json=websocket.send_json, close=websocket.close)
    await broker.register(conn)
    logger.info("Worker tunnel connected for node %s", node_id)
    watchdog = asyncio.create_task(_revalidate(websocket, conn, credential_hash))
    try:
        await broker.handle_messages(conn, websocket.receive_text)
    except WebSocketDisconnect:
        pass
    finally:
        watchdog.cancel()
        broker.unregister(conn)
        logger.info("Worker tunnel closed for node %s", node_id)


# Tunnel close codes the worker acts on: 4401 revoked (stop and forget the credential), 4403 blocked by an operator
# (keep the credential, retry later), 4408 session expired (renew the session and reconnect).
CLOSE_CODES = {"revoked": 4401, "blocked": 4403, "session_expired": 4408, "unverifiable": 4408}


async def _revalidate(websocket: WebSocket, conn: WorkerConnection, credential_hash: str | None) -> None:
    """Close the tunnel once its node is revoked, quarantined or re-keyed, even if the disconnect message sent at
    that moment was lost (e.g. a Redis hiccup between replicas). Doubt counts as revoked."""
    while True:
        await asyncio.sleep(settings.TUNNEL_REVALIDATE_SECONDS)
        try:
            reason = await worker_service.still_authorized(conn.node_id, credential_hash)
        except Exception:  # noqa: BLE001
            logger.exception("Could not re-check node %s; closing its tunnel", conn.node_id)
            reason = "unverifiable"
        if reason is not None:
            security_events.emit("node.tunnel_closed", node_id=conn.node_id, reason=reason)
            broker.unregister(conn)
            with contextlib.suppress(Exception):
                await websocket.close(code=CLOSE_CODES.get(reason, 4401))
            return
