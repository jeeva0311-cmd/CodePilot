"""Conversation and Message ORM models."""
import uuid
from datetime import datetime
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Integer
from sqlalchemy.orm import relationship
from app.database.database import Base


def _uuid():
    return str(uuid.uuid4())


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String, primary_key=True, default=_uuid)
    title = Column(String(256), default="New Conversation")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    workspace_path = Column(Text, default="")

    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan", order_by="Message.created_at")
    tasks = relationship("AgentTask", back_populates="conversation", cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True, default=_uuid)
    conversation_id = Column(String, ForeignKey("conversations.id"), nullable=False)
    role = Column(String(32), nullable=False)   # user | assistant | system | tool
    content = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
    message_type = Column(String(64), default="text")  # text | plan | tool_call | tool_result | approval
    metadata_json = Column(Text, default="{}")

    conversation = relationship("Conversation", back_populates="messages")
