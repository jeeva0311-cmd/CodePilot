"""
Agent execution loop — runs in a background thread.
Drives the agentic workflow: plan → tool calls → verify → summarize.
"""
import json
import logging
import re
import time
import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

from app.agent.agent import CodePilotAgent
from app.config import settings
from app.models import AgentTask, TaskStep, ToolExecution, FileChange, ApprovalRequest
from app.services.event_bus import event_bus
from app.services.approval_service import approval_service
from app.security.sandbox import get_tool_risk

logger = logging.getLogger("codepilot.loop")

# In-memory cancellation flags: task_id → bool
_cancel_flags: dict[str, bool] = {}

# Patterns that clearly indicate a conversational (non-coding-task) message
_CONVERSATIONAL_PATTERNS = [
    r"^\s*(hi|hello|hey|good (morning|afternoon|evening)|howdy|greetings)[!.,\s]*$",
    r"^\s*how are you[?!.,\s]*$",
    r"^\s*what (is|are|can) (you|this|codepilot)[?.,\s]",
    r"^\s*(thanks?|thank you|cheers|great|awesome|cool)[!.,\s]*$",
    r"^\s*(yes|no|ok|okay|sure|alright)[!.,\s]*$",
    r"i want to learn",
    r"can you help me",
    r"explain (to me )?what",
    r"explain (to me )?how",
    r"what (is|are) [a-z]",
    r"how do(es)? [a-z]",
    r"give me an example",
    r"show me (an )?example",
    r"what's the difference between",
    r"teach me",
]
_CONV_RE = [re.compile(p, re.IGNORECASE) for p in _CONVERSATIONAL_PATTERNS]

# Patterns that clearly indicate a file/code task needing tools
_CODING_TASK_PATTERNS = [
    r"inspect (the |my |this )?project",
    r"(create|write|build|make|generate) (a |an )?(file|class|function|script|app|test|calculator|api)",
    r"(fix|debug|find|identify) (the |a |this )?(bug|error|issue|problem)",
    r"(read|open|show) (the |this )?(file|code|source)",
    r"run (the |my |the )?(test|command|script)",
    r"(list|show) (the |all )?(files|directory)",
    r"git (status|log|diff)",
    r"search (the |my |this )?(code|codebase|project)",
    r"refactor",
    r"add (a |an )?(feature|function|method|endpoint)",
    r"modify|update|change (the |this |my )?code",
]
_TASK_RE = [re.compile(p, re.IGNORECASE) for p in _CODING_TASK_PATTERNS]


def _is_conversational(prompt: str) -> bool:
    """Return True if the prompt looks like a general question/conversation rather than a coding task."""
    p = prompt.strip()
    # Short messages are likely conversational (unless they match coding patterns)
    if any(r.search(p) for r in _TASK_RE):
        return False
    if any(r.search(p) for r in _CONV_RE):
        return True
    # Short prompt with no code-task keywords → treat as conversational
    if len(p) < 80 and not any(kw in p.lower() for kw in [
        "file", "code", "project", "run", "test", "debug", "build",
        "create", "write", "fix", "error", "bug", "script", "function"
    ]):
        return True
    return False


def cancel_task(task_id: str):
    _cancel_flags[task_id] = True


def _is_cancelled(task_id: str) -> bool:
    return _cancel_flags.get(task_id, False)


def _emit(task_id: str, event_type: str, data: dict):
    event_bus.publish(task_id, event_type, data)


class AgentLoop:
    def __init__(self, task: AgentTask, db: Session):
        self.task = task
        self.db = db
        self.task_id = task.id
        self.workspace = task.workspace_path
        self.agent = CodePilotAgent(self.workspace)
        self.max_iterations = settings.MAX_AGENT_ITERATIONS
        self.iteration = 0
        self.files_read: list[str] = []
        self.files_created: list[str] = []
        self.files_modified: list[str] = []
        self.errors_encountered: list[str] = []

    # ── Public entry point ─────────────────────────────────────────────────────
    def run(self):
        self._update_task_status("running", started=True)
        _emit(self.task_id, "agent_started", {
            "prompt": self.task.prompt,
            "workspace": self.workspace,
        })

        try:
            self._execute()
        except Exception as exc:
            logger.error(f"Loop error for task {self.task_id}: {exc}", exc_info=True)
            self._update_task_status("failed", error=str(exc))
            _emit(self.task_id, "task_failed", {"error": str(exc)})
        finally:
            _cancel_flags.pop(self.task_id, None)

    # ── Core execution ─────────────────────────────────────────────────────────
    def _execute(self):
        prompt = self.task.prompt

        # ── Conversational shortcut ────────────────────────────────────────────
        # For simple questions or greetings, skip planning, skip RAG, and go
        # straight to a single LLM call with no tools offered.
        if _is_conversational(prompt):
            self._execute_conversational(prompt)
            return

        # ── Full agentic mode ──────────────────────────────────────────────────
        # RAG: only retrieve context for coding tasks (not conversations)
        rag_context = self._get_rag_context(prompt)

        _emit(self.task_id, "planning", {"message": "Generating task plan…"})
        plan = self.agent.generate_plan(prompt)
        self._save_plan(plan)
        _emit(self.task_id, "plan_generated", {"plan": plan})
        self.agent.planner.start_first()

        task_msg = f"Workspace: {self.workspace}\n\nTask: {prompt}"
        if rag_context:
            task_msg += f"\n\n---\n**Relevant workspace context (from RAG):**\n{rag_context}"
            _emit(self.task_id, "rag_context", {"chunks": len(rag_context.splitlines())})
        self.agent.add_user_message(task_msg)

        final_response = ""
        while self.iteration < self.max_iterations:
            if _is_cancelled(self.task_id):
                self._update_task_status("cancelled")
                _emit(self.task_id, "task_cancelled", {
                    "message": "Task cancelled by user.",
                    "iterations": self.iteration,
                })
                return

            self.iteration += 1
            _emit(self.task_id, "iteration_started", {
                "iteration": self.iteration,
                "max": self.max_iterations,
                "plan": self.agent.planner.steps,
            })

            try:
                step_result = self.agent.step()
            except (ValueError, ConnectionError) as exc:
                self._update_task_status("failed", error=str(exc))
                _emit(self.task_id, "task_failed", {"error": str(exc)})
                return

            if step_result["type"] == "text":
                final_response = step_result.get("content") or ""
                if final_response.strip():
                    _emit(self.task_id, "agent_message", {"content": final_response})
                if step_result["finish_reason"] in ("stop", "end_turn", "length", "eos_token"):
                    if not final_response.strip():
                        final_response = self._build_summary()
                    break

            elif step_result["type"] == "tool_calls":
                if step_result.get("content"):
                    _emit(self.task_id, "agent_message", {"content": step_result["content"]})

                for tc in step_result["tool_calls"]:
                    if _is_cancelled(self.task_id):
                        break
                    self._handle_tool_call(tc)

                self._save_plan(self.agent.planner.steps)
                _emit(self.task_id, "plan_updated", {"plan": self.agent.planner.steps})

        else:
            limit_msg = (
                f"Reached the maximum iteration limit ({self.max_iterations}). "
                "The task may be incomplete. Here is a summary of what was accomplished:\n\n"
                + self._build_summary()
            )
            _emit(self.task_id, "agent_message", {"content": limit_msg})
            final_response = limit_msg

        if not final_response:
            final_response = self._build_summary()

        self._save_final(final_response)
        # Persist to conversation so it loads in history
        self._persist_assistant_message(final_response)
        self._update_task_status("completed")
        _emit(self.task_id, "task_completed", {
            "final_response": final_response,
            "iterations": self.iteration,
            "files_created": self.files_created,
            "files_modified": self.files_modified,
            "files_read": self.files_read,
            "errors": self.errors_encountered,
        })

    # ── Conversational mode (no tools, no plan, no RAG) ───────────────────────
    def _execute_conversational(self, prompt: str):
        """
        Single LLM call without any tool schemas — for greetings, learning questions,
        general help requests. Much faster and always produces a text response.
        """
        logger.info(f"Conversational mode for task {self.task_id}")
        self.iteration = 1

        # Build a simple message: just the user prompt, no workspace noise
        from app.agent.llm_client import llm_client
        from app.agent.prompts import SYSTEM_PROMPT

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ]

        try:
            # No tools — the model is free to respond as a conversational AI
            result = llm_client.chat(
                messages=messages,
                tools=None,         # explicitly no tools
                max_tokens=settings.OPENAI_MAX_TOKENS,
            )
        except (ValueError, ConnectionError) as exc:
            self._update_task_status("failed", error=str(exc))
            _emit(self.task_id, "task_failed", {"error": str(exc)})
            return

        content = result.get("content") or ""

        # Some models return empty content; ask again without system-prompt clutter
        if not content.strip():
            try:
                result2 = llm_client.chat(
                    messages=[{"role": "user", "content": prompt}],
                    tools=None,
                    max_tokens=settings.OPENAI_MAX_TOKENS,
                )
                content = result2.get("content") or ""
            except Exception:
                pass

        if not content.strip():
            # Absolute fallback — the LLM gave us nothing usable
            content = (
                "I'm here to help! Could you give me more detail about what you'd like to do? "
                "I can help with coding tasks, explain programming concepts, or work with your project files."
            )

        _emit(self.task_id, "agent_message", {"content": content})
        self._save_final(content)
        # Persist assistant message to conversation so it loads in history
        self._persist_assistant_message(content)
        self._update_task_status("completed")
        _emit(self.task_id, "task_completed", {
            "final_response": content,
            "iterations": 1,
            "files_created": [],
            "files_modified": [],
            "files_read": [],
            "errors": [],
        })

    # ── Tool call handling ─────────────────────────────────────────────────────
    def _handle_tool_call(self, tc: dict):
        tool_name = tc["name"]
        arguments = tc["arguments"]
        tc_id = tc["id"]
        risk = get_tool_risk(tool_name)

        _emit(self.task_id, "tool_started", {
            "tool": tool_name,
            "arguments": arguments,
            "risk": risk,
            "iteration": self.iteration,
        })

        need_approval = (
            (risk == "high" and settings.REQUIRE_APPROVAL_FOR_HIGH_RISK) or
            (risk == "medium" and settings.REQUIRE_APPROVAL_FOR_MEDIUM_RISK)
        )

        if need_approval:
            decision = self._request_approval(tool_name, arguments, risk)
            if decision != "approved":
                result = {"success": False, "error": "Operation rejected by user.", "rejected": True}
                self.agent.record_tool_result(tc_id, tool_name, result)
                _emit(self.task_id, "tool_rejected", {"tool": tool_name, "reason": "User rejected the operation."})
                self._save_tool_execution(tool_name, arguments, result, risk, 0, "rejected")
                return

        start = time.time()
        result = self.agent.execute_tool(tool_name, arguments)
        duration = round(time.time() - start, 3)

        self._track_changes(tool_name, arguments, result)
        status = "completed" if result.get("success", True) and "error" not in result else "failed"
        self._save_tool_execution(tool_name, arguments, result, risk, duration, status)
        self.agent.record_tool_result(tc_id, tool_name, result)

        _emit(self.task_id, "tool_completed", {
            "tool": tool_name,
            "status": status,
            "duration": duration,
            "result_summary": self._summarize_result(tool_name, result),
        })

        if status == "failed":
            self.errors_encountered.append(f"{tool_name}: {result.get('error', 'Unknown error')}")

    # ── Approval flow ──────────────────────────────────────────────────────────
    def _request_approval(self, tool_name: str, arguments: dict, risk: str) -> str:
        summary = self._describe_operation(tool_name, arguments)
        approval_id = str(uuid.uuid4())

        req = ApprovalRequest(
            id=approval_id,
            task_id=self.task_id,
            tool_name=tool_name,
            operation_summary=summary,
            risk_level=risk,
            input_json=json.dumps(arguments, default=str),
            status="pending",
        )
        self.db.add(req)
        self.db.commit()

        approval_service.register(approval_id)
        _emit(self.task_id, "approval_requested", {
            "approval_id": approval_id,
            "tool": tool_name,
            "summary": summary,
            "risk": risk,
            "arguments": arguments,
        })

        decision = approval_service.wait(approval_id, timeout=300.0)

        if decision == "timeout":
            _emit(self.task_id, "approval_timeout", {"approval_id": approval_id})
            return "rejected"

        _emit(self.task_id, f"approval_{decision}", {"approval_id": approval_id, "tool": tool_name})
        return decision

    # ── RAG helper ─────────────────────────────────────────────────────────────
    def _get_rag_context(self, query: str) -> str:
        """Retrieve semantically relevant chunks — only for non-trivial coding tasks."""
        try:
            if not settings.RAG_ENABLED:
                return ""
            # Skip RAG for short or conversational queries
            if len(query.strip()) < 20:
                return ""
            from app.rag.store import rag_store
            chunks = rag_store.query(self.workspace, query, top_k=settings.RAG_TOP_K)
            if not chunks:
                return ""
            # Only include chunks with meaningful relevance (score > 0.4)
            relevant = [c for c in chunks if c.get("score", 0) > 0.4]
            if not relevant:
                return ""
            lines = []
            for c in relevant:
                lines.append(f"[{c['file']}] (score={c['score']:.2f})\n{c['text'][:400]}")
            return "\n\n".join(lines)
        except Exception as exc:
            logger.debug(f"RAG context retrieval failed: {exc}")
            return ""

    # ── Misc helpers ───────────────────────────────────────────────────────────
    def _describe_operation(self, tool_name: str, args: dict) -> str:
        if tool_name == "write_file":
            return f"Create/overwrite file: {args.get('path', '?')}"
        if tool_name == "edit_file":
            return f"Edit file: {args.get('path', '?')}"
        if tool_name == "run_command":
            return f"Run command: {args.get('command', '?')}"
        if tool_name == "run_tests":
            return f"Run tests in: {args.get('test_path', 'workspace')}"
        return f"Execute {tool_name} with args: {json.dumps(args, default=str)[:120]}"

    def _track_changes(self, tool_name: str, args: dict, result: dict):
        if not result.get("success", True) or "error" in result:
            return
        if tool_name == "read_file":
            path = args.get("path", "")
            if path and path not in self.files_read:
                self.files_read.append(path)
        elif tool_name == "write_file":
            path = args.get("path", "")
            action = result.get("action", "created")
            self._save_file_change(path, action)
            if action == "created":
                if path not in self.files_created: self.files_created.append(path)
            else:
                if path not in self.files_modified: self.files_modified.append(path)
        elif tool_name == "edit_file":
            path = args.get("path", "")
            if path:
                self._save_file_change(path, "modified")
                if path not in self.files_modified: self.files_modified.append(path)

    def _summarize_result(self, tool_name: str, result: dict) -> str:
        if "error" in result:
            return f"Error: {result['error']}"
        if tool_name == "list_files":    return f"Listed {result.get('total_shown', 0)} files"
        if tool_name == "read_file":     return f"Read {result.get('lines', 0)} lines from {result.get('path', '')}"
        if tool_name in ("write_file", "edit_file"): return f"{result.get('action', 'done')} — {result.get('path', '')}"
        if tool_name == "run_command":   return f"Exit code {result.get('exit_code', '?')} in {result.get('duration_seconds', 0):.1f}s"
        if tool_name == "run_tests":
            s = result.get("summary", {}); return f"Tests: {s.get('passed',0)} passed, {s.get('failed',0)} failed"
        if tool_name == "search_files":  return f"{result.get('total_matches', 0)} matches found"
        if tool_name == "get_project_info":
            langs = ", ".join(result.get("languages", [])); return f"Languages: {langs or 'unknown'}"
        if tool_name == "git_status":    return f"Branch: {result.get('branch', '?')}"
        return "Done"

    def _build_summary(self) -> str:
        lines = ["## Task Summary"]
        if self.files_created:  lines.append(f"**Files created:** {', '.join(self.files_created)}")
        if self.files_modified: lines.append(f"**Files modified:** {', '.join(self.files_modified)}")
        if self.files_read:     lines.append(f"**Files read:** {', '.join(self.files_read[:10])}")
        if self.errors_encountered: lines.append(f"**Errors encountered:** {len(self.errors_encountered)}")
        lines.append(f"**Iterations used:** {self.iteration}/{self.max_iterations}")
        return "\n".join(lines)

    # ── DB persistence ─────────────────────────────────────────────────────────
    def _update_task_status(self, status: str, started: bool = False, error: str = ""):
        task = self.db.query(AgentTask).filter(AgentTask.id == self.task_id).first()
        if task:
            task.status = status
            task.iterations = self.iteration
            if started: task.started_at = datetime.utcnow()
            if status in ("completed", "failed", "cancelled"):
                task.completed_at = datetime.utcnow()
                if task.started_at:
                    task.duration_seconds = (task.completed_at - task.started_at).total_seconds()
            if error: task.error_message = error
            self.db.commit()

    def _save_plan(self, plan: list):
        task = self.db.query(AgentTask).filter(AgentTask.id == self.task_id).first()
        if task:
            task.plan_json = json.dumps(plan)
            self.db.commit()

    def _save_final(self, response: str):
        task = self.db.query(AgentTask).filter(AgentTask.id == self.task_id).first()
        if task:
            task.final_response = response
            task.iterations = self.iteration
            self.db.commit()

    def _save_tool_execution(self, tool_name, args, result, risk, duration, status):
        te = ToolExecution(
            task_id=self.task_id,
            tool_name=tool_name,
            input_json=json.dumps(args, default=str),
            output_json=json.dumps(result, default=str)[:4000],
            status=status,
            risk_level=risk,
            completed_at=datetime.utcnow(),
            duration_seconds=duration,
            error_message=result.get("error", ""),
        )
        self.db.add(te)
        self.db.commit()

    def _save_file_change(self, path: str, change_type: str):
        fc = FileChange(task_id=self.task_id, file_path=path, change_type=change_type)
        self.db.add(fc)
        self.db.commit()

    def _persist_assistant_message(self, content: str):
        """Save the assistant's final response to the conversation's message history."""
        if not content or not self.task.conversation_id:
            return
        try:
            from app.models.conversation import Message
            msg = Message(
                conversation_id=self.task.conversation_id,
                role="assistant",
                content=content,
                message_type="text",
            )
            self.db.add(msg)
            self.db.commit()
        except Exception as exc:
            logger.debug(f"Failed to persist assistant message: {exc}")
