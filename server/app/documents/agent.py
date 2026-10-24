import uuid
from datetime import datetime
from typing import Any

from pydantic import Field

from app.core.timeutil import utcnow
from app.documents.base import Doc


class AgentTask(Doc):
    type: str | None = None
    status: str | None = None
    input_data: Any = None
    output_data: Any = None
    error: str | None = None
    created_at: datetime | None = Field(default_factory=utcnow)
    completed_at: datetime | None = None

    class Settings(Doc.Settings):
        name = "agent_tasks"


class AgentAction(Doc):
    task_id: uuid.UUID | None = None
    action: str | None = None
    tool_name: str | None = None
    tool_input: Any = None
    tool_output: Any = None
    reasoning: str | None = None
    created_at: datetime | None = Field(default_factory=utcnow)

    class Settings(Doc.Settings):
        name = "agent_actions"
