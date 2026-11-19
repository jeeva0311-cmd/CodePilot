"""FileChange ORM model."""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.database.database import Base


def _uuid():
    return str(uuid.uuid4())


class FileChange(Base):
    __tablename__ = "file_changes"

    id = Column(String, primary_key=True, default=_uuid)
    task_id = Column(String, ForeignKey("agent_tasks.id"), nullable=True)
    file_path = Column(Text, nullable=False)
    change_type = Column(String(32), nullable=False)  # created|modified|deleted
    created_at = Column(DateTime, default=datetime.utcnow)
    before_preview = Column(Text, default="")
    after_preview = Column(Text, default="")

    task = relationship("AgentTask", back_populates="file_changes")
