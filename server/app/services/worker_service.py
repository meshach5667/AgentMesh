"""Control-plane side of worker protocol v1: enrollment, authentication, heartbeats, the command queue,
and deployment status reports."""

import asyncio
import base64
import hmac
import secrets
import uuid
from datetime import timedelta
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, padding, rsa
from fastapi import HTTPException

from app.core import security_events, signing
from app.core.config import settings
from app.core.database import Session
from app.core.ids import parse_uuid
from app.core.security import generate_secret, hash_secret, verify_node_api_key
from app.core.timeutil import utcnow
from app.documents.deployment import Deployment
from app.documents.deployment import DeploymentStatus as S
from app.documents.model import ModelArtifact
from app.documents.node import BLOCKED_NODE_STATUSES, Node, NodeHardware, NodeStatus
from app.documents.node_session import NodeChallenge, NodeSession
from app.documents.user import Provider
from app.documents.worker import CommandStatus, NodeCommand, NodeEnrollmentToken
from app.schemas.worker import (
    Allocation,
    CommandOut,
    DeploymentStatusReport,
    EnrollRequest,
    HardwareReport,
    HeartbeatRequest,
    HeartbeatResponse,
    SigningKey,
)
from app.services import audit_service, node_pricing_service, placement_service, release_service
from app.services import deployment_lifecycle as lifecycle
from app.services.commands import cancel_undelivered, enqueue_command  # noqa: F401  (re-exported)
from app.services.scheduler_service import release_reservation

ENROLL_TOKEN_PREFIX = "am_enroll_"
NODE_CREDENTIAL_PREFIX = "am_node_"
NODE_SESSION_PREFIX = "am_ns_"
CHALLENGE_TTL_SECONDS = 60


# --- Enrollment -----------------------------------------------------------------------------------------


async def create_enrollment_token(db: Session, user_id, name: str | None, region: str | None) -> dict:
    provider = await db.find_one(Provider, {"user_id": user_id})
    if not provider:
        raise HTTPException(status_code=403, detail="Provider account required")
    token = generate_secret(ENROLL_TOKEN_PREFIX)
    expires_at = utcnow() + timedelta(minutes=settings.ENROLLMENT_TOKEN_TTL_MINUTES)
    row = NodeEnrollmentToken(
        provider_id=provider.id, token_hash=hash_secret(token), name=name, region=region, expires_at=expires_at
    )
    db.add(row)
    await db.flush()
    audit_service.record(
        db,
        actor_id=user_id,
        action="node.enrollment_token_created",
        resource_type="enrollment_token",
        resource_id=row.id,
        details={"name": name, "region": region},
    )
    await db.commit()
    return {"token": token, "expires_at": expires_at}


def _clamp_allocation(alloc: Allocation, hw: HardwareReport) -> Allocation:
    """A worker cannot allocate more than the hardware it reports. (Reported hardware itself is unverified.)"""
    total_vram = sum(g.vram_mb for g in hw.gpus)
    return Allocation(
        cpu_cores=min(alloc.cpu_cores, hw.cpu_cores),
        ram_mb=min(alloc.ram_mb, hw.ram_mb),
        disk_mb=min(alloc.disk_mb, hw.disk_free_mb),
        vram_mb=min(alloc.vram_mb, total_vram),
    )


def _apply_capabilities(node: Node, hw: HardwareReport | None, alloc: Allocation | None, runtimes) -> None:
    if hw is not None and alloc is not None:
        alloc = _clamp_allocation(alloc, hw)
    if alloc is not None:
        node.allocated_cpu_cores = alloc.cpu_cores
        node.allocated_ram_mb = alloc.ram_mb
        node.allocated_disk_mb = alloc.disk_mb
        node.allocated_vram_mb = alloc.vram_mb
    if runtimes is not None:
        node.runtimes = [r.model_dump() for r in runtimes]


async def enroll(db: Session, req: EnrollRequest) -> dict:
    if req.protocol_version not in settings.WORKER_PROTOCOL_VERSIONS:
        raise HTTPException(status_code=426, detail="Unsupported worker protocol version")

    now = utcnow()
    token_hash = hash_secret(req.token)
    # Claim the token atomically so it can be used exactly once.
    claimed = await db.update_one(
        NodeEnrollmentToken,
        {"token_hash": token_hash, "used_at": None, "expires_at": {"$gt": now}},
        {"$set": {"used_at": now}},
    )
    token = await db.find_one(NodeEnrollmentToken, {"token_hash": token_hash}) if claimed else None
    if token is None:
        await db.rollback()
        raise HTTPException(status_code=401, detail="Enrollment token is invalid, expired, or already used")

    credential = generate_secret(NODE_CREDENTIAL_PREFIX)
    hw = req.hardware
    node = Node(
        owner_id=token.provider_id,
        name=token.name or req.name,
        region=token.region,
        public_key=req.public_key,
        api_key_hash=hash_secret(credential),
        status=NodeStatus.ONLINE,
        last_heartbeat=now,
        mode=req.mode,
        worker_version=req.worker_version,
        protocol_version=req.protocol_version,
        accepting_workloads=True,
    )
    _apply_capabilities(node, hw, req.allocation, req.runtimes)
    db.add(node)
    await db.flush()
    await node_pricing_service.apply_provider_default(db, node)
    gpu = hw.gpus[0] if hw.gpus else None
    db.add(
        NodeHardware(
            node_id=node.id,
            cpu_model=hw.cpu_model,
            cpu_cores=hw.cpu_cores,
            ram_gb=hw.ram_mb // 1024,
            storage_gb=hw.disk_free_mb // 1024,
            gpu_model=gpu.model if gpu else None,
            gpu_count=len(hw.gpus),
            gpu_vram_gb=(gpu.vram_mb // 1024) if gpu else None,
            os_info=f"{hw.os} {hw.arch}",
            capabilities={"gpus": [g.model_dump() for g in hw.gpus], "arch": hw.arch},
        )
    )
    token.node_id = node.id
    audit_service.record(
        db,
        actor_id=None,
        action="node.enrolled",
        resource_type="node",
        resource_id=node.id,
        details={"provider_id": str(token.provider_id), "mode": req.mode, "worker_version": req.worker_version},
    )
    await db.commit()
    return {
        "node_id": node.id,
        "node_credential": credential,
        "protocol_version": req.protocol_version,
        "heartbeat_interval_seconds": settings.WORKER_HEARTBEAT_INTERVAL_SECONDS,
        "command_signing_key": signing.signing_key_info(),
    }


async def authenticate_worker(
    db: Session,
    node_id: str | None,
    credential: str | None,
    protocol: str | None,
    *,
    enrollment_credential: bool = False,
) -> Node:
    """Authenticate a worker by node id plus a node session token, or (legacy, while ALLOW_LEGACY_NODE_CREDENTIALS)
    its long-lived enrollment credential. ``enrollment_credential`` requires the long-lived credential itself: only
    the session endpoints use it, together with a signature by the node key."""
    if protocol is not None:
        try:
            version = int(protocol)
        except ValueError:
            version = -1
        if version not in settings.WORKER_PROTOCOL_VERSIONS:
            raise HTTPException(status_code=426, detail="Unsupported worker protocol version")
    if not node_id or not credential:
        raise HTTPException(status_code=401, detail="Node credentials required")
    try:
        node = await db.get(Node, parse_uuid(node_id, "Node"))
    except HTTPException:
        node = None
    invalid = HTTPException(status_code=401, detail="Invalid node credentials")
    if node is None:
        raise invalid
    if credential.startswith(NODE_SESSION_PREFIX) and not enrollment_credential:
        session = await db.find_one(NodeSession, {"token_hash": hash_secret(credential)})
        if session is None or session.node_id != node.id or session.revoked_at is not None:
            raise invalid
        if session.expires_at <= utcnow():
            raise HTTPException(status_code=401, detail="Node session expired")
    else:
        if not verify_node_api_key(credential, node.api_key_hash):
            raise invalid
        if not (enrollment_credential or settings.ALLOW_LEGACY_NODE_CREDENTIALS):
            raise HTTPException(status_code=401, detail="Node session required")
    if node.status == NodeStatus.REVOKED:
        raise HTTPException(status_code=401, detail="Node credential revoked")
    if node.status in BLOCKED_NODE_STATUSES:
        raise HTTPException(status_code=403, detail="Node suspended")
    return node


async def _ensure_still_active(node: Node) -> None:
    """Re-check a node authenticated at the start of a long request. Revocation deletes its credential and ends its
    sessions; quarantine and suspension change its status. Raises the same errors authentication would."""
    from app.core.database import session_scope

    async with session_scope() as db:
        fresh = await db.get(Node, node.id)
    if fresh is None or fresh.status == NodeStatus.REVOKED or fresh.api_key_hash != node.api_key_hash:
        raise HTTPException(status_code=401, detail="Node credential revoked")
    if fresh.status in BLOCKED_NODE_STATUSES:
        raise HTTPException(status_code=403, detail="Node suspended")


async def still_authorized(node_id: uuid.UUID, credential_hash: str | None) -> str | None:
    """Why a node authenticated earlier must drop its connection, or None if it may keep it. Reasons: "revoked"
    (gone, revoked, or its credential replaced), "blocked" (quarantined or suspended), "session_expired" (renew
    and reconnect). A renewed session keeps a tunnel opened with an earlier session of the same node valid."""
    from app.core.database import session_scope

    async with session_scope() as db:
        node = await db.get(Node, node_id)
        if node is None or node.status == NodeStatus.REVOKED:
            return "revoked"
        if node.status in BLOCKED_NODE_STATUSES:
            return "blocked"
        if credential_hash is not None and credential_hash == node.api_key_hash:
            return None if settings.ALLOW_LEGACY_NODE_CREDENTIALS else "session_expired"
        session = await db.find_one(NodeSession, {"token_hash": credential_hash})
        if session is None or session.node_id != node.id or session.revoked_at is not None:
            return "revoked"
        live = await db.count(NodeSession, {"node_id": node.id, "revoked_at": None, "expires_at": {"$gt": utcnow()}})
        return None if live else "session_expired"


# --- Node sessions (proof of possession) --------------------------------------------------------------


def _verify_node_signature(public_key_pem: str | None, message: bytes, signature: bytes) -> bool:
    """Verify with the key the node registered at enrollment: RSA (2048+ bits, PSS/SHA-256) or Ed25519."""
    if not public_key_pem:
        return False
    try:
        key = serialization.load_pem_public_key(public_key_pem.encode())
        if isinstance(key, rsa.RSAPublicKey):
            if key.key_size < 2048:
                return False
            key.verify(
                signature,
                message,
                padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.AUTO),
                hashes.SHA256(),
            )
        elif isinstance(key, ed25519.Ed25519PublicKey):
            key.verify(signature, message)
        else:
            return False
    except (InvalidSignature, ValueError, TypeError):
        return False
    return True


def session_message(node_id: Any, challenge: str) -> bytes:
    return f"agentmesh-node-session-v1.{node_id}.{challenge}".encode()


async def issue_challenge(db: Session, node: Node) -> dict:
    challenge = secrets.token_urlsafe(32)
    db.add(
        NodeChallenge(
            node_id=node.id,
            challenge_hash=hash_secret(challenge),
            expires_at=utcnow() + timedelta(seconds=CHALLENGE_TTL_SECONDS),
        )
    )
    await db.commit()
    return {"challenge": challenge, "expires_in": CHALLENGE_TTL_SECONDS}


async def create_session(db: Session, node: Node, challenge: str, signature_b64: str) -> dict:
    """Exchange a signed challenge for a short-lived session token. Each challenge works once."""
    now = utcnow()
    refused = HTTPException(status_code=401, detail="Challenge or signature invalid")
    claimed = await db.update_one(
        NodeChallenge,
        {"challenge_hash": hash_secret(challenge), "node_id": node.id, "used_at": None, "expires_at": {"$gt": now}},
        {"$set": {"used_at": now}},
    )
    try:
        signature = base64.b64decode(signature_b64, validate=True)
    except ValueError:
        signature = b""
    if not claimed or not _verify_node_signature(node.public_key, session_message(node.id, challenge), signature):
        await db.commit()  # a used challenge stays used
        security_events.emit("node.session_refused", node_id=node.id)
        raise refused
    token = generate_secret(NODE_SESSION_PREFIX)
    expires = now + timedelta(minutes=settings.NODE_SESSION_TTL_MINUTES)
    db.add(NodeSession(node_id=node.id, token_hash=hash_secret(token), expires_at=expires))
    await db.commit()
    security_events.emit("node.session_issued", node_id=node.id)
    return {
        "session_token": token,
        "expires_in": settings.NODE_SESSION_TTL_MINUTES * 60,
        "command_signing_key": signing.signing_key_info(),
    }


async def revoke_sessions(db: Session, node_id: uuid.UUID) -> int:
    return await db.update_many(
        NodeSession, {"node_id": node_id, "revoked_at": None}, {"$set": {"revoked_at": utcnow()}}
    )


# --- Heartbeat and reconciliation ----------------------------------------------------------------------


async def heartbeat(db: Session, node: Node, req: HeartbeatRequest) -> HeartbeatResponse:
    now = utcnow()
    node.last_heartbeat = now
    node.status = NodeStatus.ONLINE
    node.worker_version = req.worker_version
    node.last_metrics = {k: float(v) for k, v in list(req.metrics.items())[:32]}
    _apply_capabilities(node, req.hardware, req.allocation, req.runtimes)
    node.worker_available = req.available
    node.worker_unavailable_reason = None if req.available else (req.unavailable_reason or "paused")

    stop: list[uuid.UUID] = []
    reported = {r.deployment_id: r for r in req.deployments}
    if reported:
        rows = await db.find(Deployment, {"_id": {"$in": list(reported)}})
        known = {d.id: d for d in rows}
        for dep_id, report in reported.items():
            dep = known.get(dep_id)
            if dep is None or dep.node_id != node.id or dep.deleted_at is not None:
                stop.append(dep_id)
                continue
            status = S(dep.status)
            if status in lifecycle.TERMINAL or status == S.STOPPING:
                if report.state not in ("stopped", "failed"):
                    stop.append(dep_id)
            elif status == S.READY and report.state == "running" and not report.healthy:
                await lifecycle.transition(db, dep, S.UNHEALTHY, actor="worker", message="Health check failing")
            elif status == S.UNHEALTHY and report.state == "running" and report.healthy:
                await lifecycle.transition(db, dep, S.READY, actor="worker", message="Recovered", last_health_at=now)
            elif status in (S.READY, S.UNHEALTHY) and report.healthy:
                dep.last_health_at = now

    # Deployments the control plane believes are serving on this node but the worker no longer reports.
    missing = await db.find(Deployment, {"node_id": node.id, "status": S.READY.value, "_id": {"$nin": list(reported)}})
    for dep in missing:
        await lifecycle.transition(
            db, dep, S.UNHEALTHY, actor="system", message="Worker no longer reports this workload"
        )

    await db.commit()
    return HeartbeatResponse(
        server_time=now.timestamp(),
        accepting_workloads=bool(node.accepting_workloads),
        heartbeat_interval_seconds=settings.WORKER_HEARTBEAT_INTERVAL_SECONDS,
        stop_deployments=stop,
        latest_worker_version=release_service.latest_version(),
        command_signing_key=SigningKey(**signing.signing_key_info()),
    )


async def disconnect(db: Session, node: Node) -> None:
    """Graceful worker shutdown: stop scheduling onto the node right away instead of waiting for the
    heartbeat timeout, and handle its deployments like any other node loss."""
    from app.background.monitors import handle_node_loss

    node.status = NodeStatus.OFFLINE
    await handle_node_loss(db, node, "Worker shut down")
    await db.commit()


# --- Command queue -------------------------------------------------------------------------------------


async def _lease_once(db: Session, node: Node, max_commands: int) -> list[CommandOut]:
    now = utcnow()
    candidates = await db.find(
        NodeCommand,
        {
            "node_id": node.id,
            "$or": [
                {"status": CommandStatus.PENDING.value},
                {"status": CommandStatus.LEASED.value, "lease_expires_at": {"$lt": now}},
            ],
            "$expr": {"$lt": ["$attempts", "$max_attempts"]},
        },
        sort=[("created_at", 1)],
        limit=max_commands,
    )
    leased: list[CommandOut] = []
    for cmd in candidates:
        claimed = await db.update_one(
            NodeCommand,
            {"_id": cmd.id, "status": cmd.status, "attempts": cmd.attempts},
            {
                "$set": {
                    "status": CommandStatus.LEASED.value,
                    "attempts": cmd.attempts + 1,
                    "lease_expires_at": now + timedelta(seconds=settings.COMMAND_LEASE_SECONDS),
                    "updated_at": now,
                }
            },
        )
        if claimed:
            # Each delivery gets its own signed authorization; only its nonce is accepted in the ack.
            authorization, nonce, expires = signing.authorize_command(
                command_id=cmd.id,
                node_id=node.id,
                command_type=cmd.type,
                deployment_id=cmd.deployment_id,
                payload=cmd.payload or {},
            )
            await db.update_one(
                NodeCommand, {"_id": cmd.id}, {"$set": {"auth_nonce": nonce, "auth_expires_at": expires}}
            )
            leased.append(
                CommandOut(
                    id=cmd.id,
                    type=cmd.type,
                    deployment_id=cmd.deployment_id,
                    payload=cmd.payload,
                    attempt=cmd.attempts + 1,
                    authorization=authorization,
                )
            )
    await db.commit()
    return leased


async def poll_commands(db: Session, node: Node, max_commands: int, wait_seconds: int) -> list[CommandOut]:
    """Long-poll: return as soon as commands exist, or after ``wait_seconds`` with an empty list."""
    deadline = asyncio.get_running_loop().time() + wait_seconds
    first = True
    while True:
        # A node revoked, quarantined or re-keyed during the wait must not lease work at the end of it.
        if not first:
            await _ensure_still_active(node)
        first = False
        leased = await _lease_once(db, node, max_commands)
        if leased or asyncio.get_running_loop().time() >= deadline:
            return leased
        await asyncio.sleep(1.0)


async def ack_command(
    db: Session, node: Node, command_id: str, status: str, error: str | None, nonce: str | None = None
) -> None:
    cmd = await db.get(NodeCommand, parse_uuid(command_id, "Command"))
    if cmd is None or cmd.node_id != node.id:
        raise HTTPException(status_code=404, detail="Command not found")
    if cmd.status in (CommandStatus.SUCCEEDED.value, CommandStatus.FAILED.value, CommandStatus.CANCELLED.value):
        return  # duplicate ack: idempotent
    # Workers that verify authorizations echo the nonce of the delivery they acted on; an ack carrying the nonce of
    # an earlier, superseded delivery is a replay. (Older workers send none, accepted while legacy mode is on.)
    if nonce is not None and not hmac.compare_digest(nonce, cmd.auth_nonce or ""):
        raise HTTPException(status_code=409, detail="Command authorization superseded")
    if nonce is None and not settings.ALLOW_LEGACY_NODE_CREDENTIALS:
        raise HTTPException(status_code=422, detail="Command acknowledgement needs the authorization nonce")
    now = utcnow()
    cmd.status = CommandStatus.FAILED.value if status == "failed" else CommandStatus.SUCCEEDED.value
    cmd.error = error
    cmd.completed_at = now
    if status == "failed" and cmd.deployment_id:
        dep = await db.get(Deployment, cmd.deployment_id)
        if dep and S(dep.status) not in lifecycle.TERMINAL and dep.node_id == node.id:
            await placement_service.fail_or_reschedule(
                db,
                dep,
                code="WORKER_REJECTED",
                message=error or f"{cmd.type} command failed",
                actor="worker",
                cleanup_old_node=False,
            )
    await db.commit()


def deployment_endpoint(dep: Deployment) -> str:
    """Runtime-native base URL: Ollama deployments also expose Ollama's own API under /ollama; every runtime
    exposes the OpenAI-compatible API under /v1."""
    base = f"{settings.PUBLIC_BASE_URL}{settings.API_V1_PREFIX}/deployments/{dep.id}"
    return f"{base}/ollama" if dep.runtime == "ollama" else f"{base}/v1"


# --- Deployment status reports -------------------------------------------------------------------------


async def report_deployment_status(db: Session, node: Node, deployment_id: str, report: DeploymentStatusReport) -> dict:
    dep = await db.get(Deployment, parse_uuid(deployment_id, "Deployment"))
    if dep is None or dep.node_id != node.id:
        raise HTTPException(status_code=404, detail="Deployment not found")

    current = S(dep.status)
    now = utcnow()
    state = report.state

    if state == "STOPPED":
        # Cleanup confirmed by the worker. Valid from STOPPING, and also after the control plane has
        # already given up on the deployment (late cleanup confirmation).
        if current == S.STOPPING:
            final = S.STOPPED if dep.was_ready else S.CANCELLED
            await lifecycle.transition(db, dep, final, actor="worker", message=report.message or "Workload stopped")
            dep.cleanup_status = "done"
            await release_reservation(db, dep.id)
        elif current in lifecycle.TERMINAL:
            dep.cleanup_status = "done"  # late confirmation; the reservation was already released
        else:
            moved = await placement_service.fail_or_reschedule(
                db,
                dep,
                code=report.error_code or "WORKLOAD_EXITED",
                message=report.message or "Workload stopped unexpectedly",
                actor="worker",
                cleanup_old_node=False,
            )
            if not moved:
                dep.cleanup_status = "done"
        await db.commit()
        return {"status": dep.status}

    if current in lifecycle.TERMINAL or current == S.STOPPING:
        # Late progress for a deployment that is being or has been stopped: ignore, the worker will be told
        # to stop via the STOP command or heartbeat reconciliation.
        return {"status": dep.status, "ignored": True}

    if state == "FAILED":
        # The worker removes its runtime before reporting FAILED, so there is nothing to clean up there.
        moved = await placement_service.fail_or_reschedule(
            db,
            dep,
            code=report.error_code or "PROVISIONING_FAILED",
            message=report.message or "Provisioning failed",
            actor="worker",
            cleanup_old_node=False,
        )
        if not moved:
            dep.cleanup_status = "done"
        await db.commit()
        return {"status": dep.status}

    target = S(state)
    if current in (S.READY, S.UNHEALTHY) and target in (S.PROVISIONING, S.STARTING):
        # Only a customer restart may take a serving deployment back to provisioning; a worker report
        # like this is stale (e.g. sent while re-adopting after its own restart).
        raise HTTPException(status_code=409, detail=f"{current.value} -> {target.value} is not allowed from a worker")
    if target == current:
        if report.message:
            await lifecycle.record_event(db, dep, actor="worker", message=report.message)
        dep.updated_at = now  # progress resets the stall timeout
        await db.commit()
        return {"status": dep.status}

    extra: dict[str, Any] = {}
    if target == S.READY:
        extra = {
            "model_digest": report.model_digest,
            "last_health_at": now,
            "endpoint": deployment_endpoint(dep),
            "started_at": dep.started_at or now,
        }
    if target == S.READY and dep.artifact_id:
        # Evidence that this model/runtime combination really serves, not just that it is in the catalog.
        artifact = await db.get(ModelArtifact, dep.artifact_id)
        if artifact is not None:
            artifact.last_ready_at = now
    try:
        ok = await lifecycle.transition(db, dep, target, actor="worker", message=report.message, **extra)
    except lifecycle.InvalidTransition as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from None
    if not ok:
        raise HTTPException(status_code=409, detail="Deployment status changed concurrently")
    await db.commit()
    return {"status": dep.status}
