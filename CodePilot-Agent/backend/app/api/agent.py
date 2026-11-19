"""
Agent task endpoints — create, monitor, cancel, stream events.
"""
import json
import threading
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional
from datetime import datetime

from app.database import get_db, SessionLocal
from app.models import AgentTask, Conversation, Message, ToolExecution, FileChange
from app.services.event_bus import event_bus
from app.workspace import workspace_manager
from app.config import settings

router = APIRouter()


class TaskCreate(BaseModel):
    prompt: str
    conversation_id: Optional[str] = None
    workspace_path: Optional[str] = None


def _task_dict(t: AgentTask) -> dict:
    return {
        "id": t.id,
        "conversation_id": t.conversation_id,
        "prompt": t.prompt,
        "status": t.status,
        "workspace_path": t.workspace_path,
        "created_at": t.created_at.isoformat() if t.created_at else None,
        "started_at": t.started_at.isoformat() if t.started_at else None,
        "completed_at": t.completed_at.isoformat() if t.completed_at else None,
        "duration_seconds": t.duration_seconds,
        "iterations": t.iterations,
        "final_response": t.final_response,
        "error_message": t.error_message,
        "plan": json.loads(t.plan_json or "[]"),
    }


@router.post("/agent/tasks", status_code=201)
def create_task(body: TaskCreate, db: Session = Depends(get_db)):
    if not settings.api_key_configured:
        raise HTTPException(400, "OpenAI API key not configured. Add OPENAI_API_KEY to your .env file.")

    ws_path = body.workspace_path or workspace_manager.path
    task = AgentTask(
        prompt=body.prompt,
        conversation_id=body.conversation_id,
        workspace_path=ws_path,
        status="pending",
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    # Save user message to conversation
    if body.conversation_id:
        msg = Message(
            conversation_id=body.conversation_id,
            role="user",
            content=body.prompt,
        )
        db.add(msg)
        conv = db.query(Conversation).filter(Conversation.id == body.conversation_id).first()
        if conv:
            conv.updated_at = datetime.utcnow()
            if conv.title == "New Conversation" and len(body.prompt) > 0:
                conv.title = body.prompt[:60] + ("…" if len(body.prompt) > 60 else "")
        db.commit()

    # Launch the agent loop in a background thread
    t = threading.Thread(target=_run_agent, args=(task.id,), daemon=True)
    t.start()

    return _task_dict(task)


@router.get("/agent/tasks/{task_id}")
def get_task(task_id: str, db: Session = Depends(get_db)):
    task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
    if not task:
        raise HTTPException(404, "Task not found")
    result = _task_dict(task)
    result["tool_executions"] = [
        {
            "id": te.id,
            "tool_name": te.tool_name,
            "status": te.status,
            "risk_level": te.risk_level,
            "input_json": te.input_json,
            "output_json": te.output_json,
            "started_at": te.started_at.isoformat() if te.started_at else None,
            "completed_at": te.completed_at.isoformat() if te.completed_at else None,
            "duration_seconds": te.duration_seconds,
            "error_message": te.error_message,
        }
        for te in task.tool_executions
    ]
    result["file_changes"] = [
        {
            "id": fc.id,
            "file_path": fc.file_path,
            "change_type": fc.change_type,
            "created_at": fc.created_at.isoformat() if fc.created_at else None,
        }
        for fc in task.file_changes
    ]
    return result


@router.post("/agent/tasks/{task_id}/cancel")
def cancel_task(task_id: str, db: Session = Depends(get_db)):
    task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
    if not task:
        raise HTTPException(404, "Task not found")
    if task.status not in ("pending", "running"):
        raise HTTPException(400, f"Task already {task.status}")

    # Set a cancellation flag the loop will pick up
    from app.agent.loop import cancel_task as _cancel
    _cancel(task_id)

    task.status = "cancelled"
    task.completed_at = datetime.utcnow()
    db.commit()
    event_bus.publish(task_id, "task_cancelled", {"message": "Task was cancelled by user."})
    return {"success": True, "task_id": task_id}


@router.get("/agent/tasks/{task_id}/events")
async def stream_events(task_id: str):
    """SSE endpoint — streams real-time events for a task."""
    return StreamingResponse(
        event_bus.stream(task_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


def _run_agent(task_id: str):
    """Run agent loop in background thread with its own DB session."""
    from app.agent.loop import AgentLoop
    db = SessionLocal()
    try:
        task = db.query(AgentTask).filter(AgentTask.id == task_id).first()
        if not task:
            return
        loop = AgentLoop(task=task, db=db)
        loop.run()
    except Exception as exc:
        import logging, traceback
        logging.getLogger("codepilot").error(f"Agent loop crashed: {exc}\n{traceback.format_exc()}")
        event_bus.publish(task_id, "task_failed", {"error": str(exc)})
    finally:
        db.close()
