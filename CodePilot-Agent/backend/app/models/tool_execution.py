"""ToolExecution ORM model."""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, Float, ForeignKey
from sqlalchemy.orm import relationship
from app.database.database import Base


def _uuid():
    return str(uuid.uuid4())


class ToolExecution(Base):
    __tablename__ = "tool_executions"

    id = Column(String, primary_key=True, default=_uuid)
    task_id = Column(String, ForeignKey("agent_tasks.id"), nullable=True)
    tool_name = Column(String(128), nullable=False)
    input_json = Column(Text, default="{}")
    output_json = Column(Text, default="{}")
    status = Column(String(32), default="pending")  # pending|running|completed|failed|rejected|cancelled
    risk_level = Column(String(16), default="low")  # low|medium|high
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    error_message = Column(Text, default="")

    task = relationship("AgentTask", back_populates="tool_executions")
