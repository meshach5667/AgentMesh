import uuid
from datetime import datetime

from pydantic import Field

from app.core.timeutil import utcnow
from app.documents.base import Doc, index, unique


class ResourceReservation(Doc):
    """Capacity held on a node for a deployment. A deployment that is moved to another node keeps its old,
    RELEASED documents as history; a partial unique index allows at most one ACTIVE one per deployment."""

    deployment_id: uuid.UUID
    node_id: uuid.UUID
    cpu_cores: int = 0
    ram_mb: int = 0
    disk_mb: int = 0
    vram_mb: int = 0
    # Unit prices in force when the deployment was placed here; it is never billed above them on this node.
    rates: dict[str, str] | None = None
    status: str = "ACTIVE"  # ACTIVE | RELEASED
    created_at: datetime = Field(default_factory=utcnow)
    released_at: datetime | None = None

    class Settings(Doc.Settings):
        name = "resource_reservations"
        indexes = [
            unique("deployment_id", name="uq_resource_reservations_active", where={"status": "ACTIVE"}),
            index("deployment_id", "status"),
            index("node_id"),
        ]
