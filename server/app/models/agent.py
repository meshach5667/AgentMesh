import uuid
from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.core.database import Base


class AgentTask(Base):
    __tablename__ = "agent_tasks"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type = Column(String(100))
    status = Column(String(50))
    input_data = Column(JSON)
    output_data = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


class AgentAction(Base):
    __tablename__ = "agent_actions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("agent_tasks.id"))
    action = Column(String(100))
    tool_name = Column(String(100))
    tool_input = Column(JSON)
    tool_output = Column(JSON, nullable=True)
    reasoning = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
