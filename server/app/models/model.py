import uuid
from datetime import datetime

from sqlalchemy import JSON, Boolean, Column, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class Model(Base):
    """Catalog entry. Appearing here does not make a model deployable: it must be approved, its runtime
    must be supported, and an eligible node with enough free capacity must exist at deploy time."""

    __tablename__ = "models"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    version = Column(String(50))
    runtime = Column(String(50))
    source = Column(String(500))
    minimum_vram = Column(Integer)
    minimum_ram = Column(Integer)
    minimum_cpu = Column(Integer)
    storage_requirement = Column(Integer)
    supported_gpu_families = Column(JSON)
    deployment_config = Column(JSON)
    is_approved = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Runtime-specific identifier, e.g. an Ollama tag such as "qwen2.5:0.5b".
    model_tag = Column(String(255), nullable=True, index=True)
    publisher = Column(String(255), nullable=True)
    family = Column(String(100), nullable=True)
    parameter_size = Column(String(50), nullable=True)
    quantization = Column(String(50), nullable=True)
    format = Column(String(50), nullable=True)
    license = Column(String(255), nullable=True)
    context_length = Column(Integer, nullable=True)
    download_size_mb = Column(Integer, nullable=True)
    # Resource requirements used by the scheduler. These are estimates unless stated otherwise.
    min_ram_mb = Column(Integer, nullable=True)
    min_disk_mb = Column(Integer, nullable=True)
    min_vram_mb = Column(Integer, nullable=True)
    min_cpu_cores = Column(Integer, nullable=True)
    gpu_required = Column(Boolean, nullable=False, default=False)
    requirements_estimated = Column(Boolean, nullable=False, default=True)
