import uuid

from fastapi import HTTPException

from app.core.database import Session
from app.core.dependencies import is_staff
from app.core.ids import parse_uuid
from app.core.security import hash_secret, verify_node_api_key
from app.core.timeutil import utcnow
from app.documents.node import BLOCKED_NODE_STATUSES, Node, NodeHardware, NodeStatus
from app.documents.user import Provider, User
from app.schemas.node import NodeCreate
from app.services import audit_service, worker_service


async def register_node(db: Session, node_data: NodeCreate, user_id: uuid.UUID):
    provider = await db.find_one(Provider, {"user_id": user_id})
    if not provider:
        raise HTTPException(status_code=403, detail="Provider account required")

    api_key = f"am_node_{uuid.uuid4().hex}"
    node = Node(
        owner_id=provider.id,
        name=node_data.name,
        public_key=node_data.public_key,
        region=node_data.region,
        api_key_hash=hash_secret(api_key),  # high-entropy key: a fast hash is appropriate
    )
    db.add(node)
    await db.flush()
    if node_data.hardware:
        db.add(NodeHardware(node_id=node.id, **node_data.hardware.model_dump()))
    await db.commit()
    await db.refresh(node)
    # The plaintext key is returned exactly once; only its hash is stored.
    return {"id": node.id, "node_id": node.id, "api_key": api_key, "status": node.status}


async def list_nodes(db: Session, user_id: uuid.UUID):
    provider = await db.find_one(Provider, {"user_id": user_id})
    if not provider:
        return []
    return await db.find(Node, {"owner_id": provider.id}, sort=[("created_at", 1)])


async def get_node(db: Session, node_id: str | uuid.UUID) -> Node:
    node = await db.get(Node, parse_uuid(node_id, "Node"))
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    return node


async def get_node_for_user(db: Session, node_id: str, user: User) -> Node:
    """Return a node only if the caller owns it or is platform staff. Other callers get 404, not 403,
    so node IDs cannot be probed."""
    node = await get_node(db, node_id)
    if is_staff(user):
        return node
    provider = await db.find_one(Provider, {"user_id": user.id})
    if not provider or node.owner_id != provider.id:
        raise HTTPException(status_code=404, detail="Node not found")
    return node


async def process_heartbeat(db: Session, node: Node):
    if node.status in BLOCKED_NODE_STATUSES:
        raise HTTPException(status_code=403, detail="Node suspended")
    node.last_heartbeat = utcnow()
    node.status = NodeStatus.ONLINE
    await db.commit()
    return {"status": "ok"}


async def authenticate_node(db: Session, node_id: str, api_key: str) -> Node:
    try:
        node = await get_node(db, node_id)
    except HTTPException:
        raise HTTPException(status_code=401, detail="Invalid node credentials") from None
    if not verify_node_api_key(api_key, node.api_key_hash):
        raise HTTPException(status_code=401, detail="Invalid node credentials")
    return node


async def set_accepting_workloads(db: Session, node_id: str, user: User, accepting: bool) -> Node:
    """Pause or resume scheduling onto a node. Existing deployments keep running (drain)."""
    node = await get_node_for_user(db, node_id, user)
    node.accepting_workloads = accepting
    audit_service.record(
        db,
        actor_id=user.id,
        action="node.resumed" if accepting else "node.paused",
        resource_type="node",
        resource_id=node.id,
    )
    await db.commit()
    await db.refresh(node)
    return node


async def set_accepts_community_models(db: Session, node_id: str, user: User, accept: bool) -> Node:
    """Provider opt-in to unreviewed community models. Opting out stops new placements; deployments already
    running keep running until they stop or move. Only the provider can consent; staff may only opt a node out."""
    node = await get_node_for_user(db, node_id, user)
    if accept and is_staff(user):
        raise HTTPException(status_code=403, detail="Only the node's provider can opt in to community models")
    node.accepts_community_models = accept
    audit_service.record(
        db,
        actor_id=user.id,
        action="node.community_models_accepted" if accept else "node.community_models_refused",
        resource_type="node",
        resource_id=node.id,
    )
    await db.commit()
    await db.refresh(node)
    return node


async def _evacuate(db: Session, node: Node, code: str, message: str, actor: str) -> None:
    """Take every active deployment off ``node`` now: fail it or move it to another node. The node is assumed
    unreachable or untrusted, so no cleanup command is queued for it (a revoked or quarantined worker stops its
    workloads itself when its connection is refused)."""
    from app.documents.deployment import Deployment
    from app.services import deployment_lifecycle as lifecycle
    from app.services import placement_service
    from app.services.scheduler_service import release_reservation

    active = await db.find(Deployment, {"node_id": node.id, "status": {"$in": [s.value for s in lifecycle.ACTIVE]}})
    for dep in active:
        if lifecycle.S(dep.status) == lifecycle.S.STOPPING:
            # Was already being stopped; the node can no longer confirm, so finish it here.
            final = lifecycle.S.STOPPED if dep.was_ready else lifecycle.S.CANCELLED
            await lifecycle.transition(db, dep, final, actor=actor, message=message)
            dep.cleanup_status = "pending_node"
            await release_reservation(db, dep.id)
            continue
        await placement_service.fail_or_reschedule(
            db, dep, code=code, message=message, actor=actor, cleanup_old_node=False
        )


async def revoke_node(db: Session, node_id: str, user: User) -> Node:
    """Revoke a node's credential (disconnect or compromise). Its active deployments fail immediately and
    their reservations are released; the worker can no longer authenticate."""
    from app.services.tunnel import broker

    node = await get_node_for_user(db, node_id, user)
    audit_service.record(
        db,
        actor_id=user.id,
        action="node.revoked",
        resource_type="node",
        resource_id=node.id,
        details={"by_role": user.role},
    )
    node.api_key_hash = None
    node.status = NodeStatus.REVOKED
    node.accepting_workloads = False
    await worker_service.revoke_sessions(db, node.id)
    actor = "operator" if is_staff(user) else "provider"
    await _evacuate(db, node, "NODE_REVOKED", "Node credential revoked", actor)
    await db.commit()
    await broker.close_node(node.id)
    await db.refresh(node)
    return node


async def quarantine_node(db: Session, node_id: str, user: User, reason: str) -> Node:
    """Cut a node off at once pending investigation (operators only). It can no longer authenticate, its tunnel is
    closed, and its deployments move elsewhere. Unlike revocation it is reversible: releasing it lets the same
    worker reconnect."""
    from app.services.tunnel import broker

    node = await get_node(db, node_id)
    if node.status == NodeStatus.REVOKED:
        raise HTTPException(status_code=409, detail="Node is revoked")
    if node.status != NodeStatus.QUARANTINED:
        node.status = NodeStatus.QUARANTINED
        node.quarantined_at = utcnow()
        node.quarantine_reason = reason
        await worker_service.revoke_sessions(db, node.id)
        await _evacuate(db, node, "NODE_QUARANTINED", "Node quarantined by an operator", "operator")
        audit_service.record(
            db,
            actor_id=user.id,
            action="node.quarantined",
            resource_type="node",
            resource_id=node.id,
            details={"reason": reason},
        )
    await db.commit()
    await broker.close_node(node.id)
    await db.refresh(node)
    return node


async def release_node(db: Session, node_id: str, user: User) -> Node:
    """End a quarantine. The node comes back OFFLINE and becomes ONLINE at its next authenticated heartbeat."""
    node = await get_node(db, node_id)
    if node.status != NodeStatus.QUARANTINED:
        raise HTTPException(status_code=409, detail="Node is not quarantined")
    node.status = NodeStatus.OFFLINE
    node.quarantined_at = node.quarantine_reason = None
    audit_service.record(db, actor_id=user.id, action="node.released", resource_type="node", resource_id=node.id)
    await db.commit()
    await db.refresh(node)
    return node
