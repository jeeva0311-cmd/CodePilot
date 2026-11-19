"""AgentTask and TaskStep ORM models."""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, Integer, Float, ForeignKey
from sqlalchemy.orm import relationship
from app.database.database import Base


def _uuid():
    return str(uuid.uuid4())


class AgentTask(Base):
    __tablename__ = "agent_tasks"

    id = Column(String, primary_key=True, default=_uuid)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=True)
    prompt = Column(Text, nullable=False)
    status = Column(String(32), default="pending")  # pending|running|completed|failed|cancelled
    workspace_path = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Float, nullable=True)
    iterations = Column(Integer, default=0)
    final_response = Column(Text, default="")
    error_message = Column(Text, default="")
    plan_json = Column(Text, default="[]")

    conversation = relationship("Conversation", back_populates="tasks")
    steps = relationship("TaskStep", back_populates="task", cascade="all, delete-orphan", order_by="TaskStep.order_index")
    tool_executions = relationship("ToolExecution", back_populates="task", cascade="all, delete-orphan")
    file_changes = relationship("FileChange", back_populates="task", cascade="all, delete-orphan")
    approval_requests = relationship("ApprovalRequest", back_populates="task", cascade="all, delete-orphan")


class TaskStep(Base):
    __tablename__ = "task_steps"

    id = Column(String, primary_key=True, default=_uuid)
    task_id = Column(String, ForeignKey("agent_tasks.id"), nullable=False)
    order_index = Column(Integer, default=0)
    description = Column(Text, nullable=False)
    status = Column(String(32), default="pending")  # pending|in_progress|completed|failed|skipped
    created_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)

    task = relationship("AgentTask", back_populates="steps")
