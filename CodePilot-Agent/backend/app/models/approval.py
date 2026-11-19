"""ApprovalRequest ORM model."""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database.database import Base


def _uuid():
    return str(uuid.uuid4())


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"

    id = Column(String, primary_key=True, default=_uuid)
    task_id = Column(String, ForeignKey("agent_tasks.id"), nullable=True)
    tool_name = Column(String(128), nullable=False)
    operation_summary = Column(Text, nullable=False)
    risk_level = Column(String(16), default="high")
    input_json = Column(Text, default="{}")
    status = Column(String(32), default="pending")  # pending|approved|rejected
    created_at = Column(DateTime, default=datetime.utcnow)
    decided_at = Column(DateTime, nullable=True)
    reason = Column(Text, default="")

    task = relationship("AgentTask", back_populates="approval_requests")
