from pydantic import BaseModel
from typing import Dict, Any, Optional
import uuid
from datetime import datetime
from app.models.deployment import DeploymentStatus

class DeploymentCreate(BaseModel):
    model_id: uuid.UUID
    config: Dict[str, Any]

class DeploymentOut(BaseModel):
    id: uuid.UUID
    customer_id: uuid.UUID
    model_id: uuid.UUID
    node_id: Optional[uuid.UUID]
    status: DeploymentStatus
    endpoint: Optional[str]
    created_at: datetime
    
    class Config:
        from_attributes = True
