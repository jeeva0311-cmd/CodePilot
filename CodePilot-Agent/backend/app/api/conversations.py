"""Conversation CRUD endpoints."""
import json
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from app.database import get_db
from app.models import Conversation, Message

router = APIRouter()


class ConversationCreate(BaseModel):
    title: str = "New Conversation"
    workspace_path: str = ""


class ConversationUpdate(BaseModel):
    title: Optional[str] = None
    workspace_path: Optional[str] = None


class MessageCreate(BaseModel):
    role: str
    content: str
    message_type: str = "text"
    metadata_json: str = "{}"


def _conv_dict(c: Conversation) -> dict:
    return {
        "id": c.id,
        "title": c.title,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "updated_at": c.updated_at.isoformat() if c.updated_at else None,
        "workspace_path": c.workspace_path,
        "message_count": len(c.messages),
    }


def _msg_dict(m: Message) -> dict:
    return {
        "id": m.id,
        "conversation_id": m.conversation_id,
        "role": m.role,
        "content": m.content,
        "created_at": m.created_at.isoformat() if m.created_at else None,
        "message_type": m.message_type,
        "metadata_json": m.metadata_json,
    }


@router.get("/conversations")
def list_conversations(db: Session = Depends(get_db)):
    convs = db.query(Conversation).order_by(Conversation.updated_at.desc()).all()
    return [_conv_dict(c) for c in convs]


@router.post("/conversations", status_code=201)
def create_conversation(body: ConversationCreate, db: Session = Depends(get_db)):
    conv = Conversation(title=body.title, workspace_path=body.workspace_path)
    db.add(conv)
    db.commit()
    db.refresh(conv)
    return _conv_dict(conv)


@router.get("/conversations/{conv_id}")
def get_conversation(conv_id: str, db: Session = Depends(get_db)):
    conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
    if not conv:
        raise HTTPException(404, "Conversation not found")
    result = _conv_dict(conv)
    result["messages"] = [_msg_dict(m) for m in conv.messages]
    return result


@router.patch("/conversations/{conv_id}")
def update_conversation(conv_id: str, body: ConversationUpdate, db: Session = Depends(get_db)):
    conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
    if not conv:
        raise HTTPException(404, "Conversation not found")
    if body.title is not None:
        conv.title = body.title
    if body.workspace_path is not None:
        conv.workspace_path = body.workspace_path
    conv.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(conv)
    return _conv_dict(conv)


@router.delete("/conversations/{conv_id}", status_code=204)
def delete_conversation(conv_id: str, db: Session = Depends(get_db)):
    conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
    if not conv:
        raise HTTPException(404, "Conversation not found")
    db.delete(conv)
    db.commit()


@router.post("/conversations/{conv_id}/messages", status_code=201)
def add_message(conv_id: str, body: MessageCreate, db: Session = Depends(get_db)):
    conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
    if not conv:
        raise HTTPException(404, "Conversation not found")
    msg = Message(
        conversation_id=conv_id,
        role=body.role,
        content=body.content,
        message_type=body.message_type,
        metadata_json=body.metadata_json,
    )
    db.add(msg)
    conv.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(msg)
    return _msg_dict(msg)


@router.get("/conversations/{conv_id}/messages")
def get_messages(conv_id: str, db: Session = Depends(get_db)):
    conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
    if not conv:
        raise HTTPException(404, "Conversation not found")
    return [_msg_dict(m) for m in conv.messages]
