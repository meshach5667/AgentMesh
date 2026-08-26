import uuid
from sqlalchemy import Column, String, Integer, Boolean, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID
from datetime import datetime
from app.core.database import Base

class Model(Base):
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
