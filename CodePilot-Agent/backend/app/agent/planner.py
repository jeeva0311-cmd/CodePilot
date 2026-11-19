"""
Task planner — asks the LLM to generate an initial step-by-step plan,
then provides helpers for updating step statuses during execution.
"""
import json
import logging
from typing import Optional

logger = logging.getLogger("codepilot.planner")


class TaskPlanner:
    def __init__(self, llm_client, workspace_path: str):
        self._llm = llm_client
        self._workspace = workspace_path
        self.steps: list[dict] = []

    def generate_plan(self, task_description: str) -> list[dict]:
        """
        Ask the LLM for a plan.  Returns a list of step dicts.
        Falls back to a minimal default plan if LLM fails.
        """
        from app.agent.prompts import PLANNING_PROMPT
        prompt = PLANNING_PROMPT.format(
            task=task_description,
            workspace=self._workspace,
        )
        try:
            result = self._llm.chat(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=800,
                temperature=0.1,
            )
            raw = result.get("content", "[]") or "[]"
            # Strip markdown code fences if present
            raw = raw.strip()
            if raw.startswith("```"):
                raw = raw.split("```")[1]
                if raw.startswith("json"):
                    raw = raw[4:]
            steps = json.loads(raw)
            if not isinstance(steps, list):
                raise ValueError("Not a list")
            self.steps = [
                {"description": s.get("description", "Step"), "status": "pending"}
                for s in steps
            ]
        except Exception as exc:
            logger.warning(f"Plan generation failed ({exc}), using default plan.")
            self.steps = [
                {"description": "Inspect project structure", "status": "pending"},
                {"description": "Analyze the task requirements", "status": "pending"},
                {"description": "Execute the task", "status": "pending"},
                {"description": "Verify results", "status": "pending"},
            ]
        return self.steps

    def mark_step(self, index: int, status: str):
        if 0 <= index < len(self.steps):
            self.steps[index]["status"] = status

    def current_step_index(self) -> int:
        for i, s in enumerate(self.steps):
            if s["status"] in ("pending", "in_progress"):
                return i
        return len(self.steps)

    def advance(self):
        """Mark the current in-progress step completed and move to next."""
        for i, s in enumerate(self.steps):
            if s["status"] == "in_progress":
                s["status"] = "completed"
                # mark next as in_progress
                if i + 1 < len(self.steps):
                    self.steps[i + 1]["status"] = "in_progress"
                return
        # If none in_progress, start the first pending one
        for s in self.steps:
            if s["status"] == "pending":
                s["status"] = "in_progress"
                return

    def start_first(self):
        if self.steps:
            self.steps[0]["status"] = "in_progress"

    def all_done(self) -> bool:
        return all(s["status"] in ("completed", "skipped", "failed") for s in self.steps)

    def to_json(self) -> str:
        return json.dumps(self.steps)
