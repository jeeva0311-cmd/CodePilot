"""
CodePilot Agent — top-level agent class.
Instantiated by the loop; wires together LLM, tools, context, planner.
"""
import json
import logging
from typing import Any, Optional

from app.agent.llm_client import llm_client
from app.agent.context import AgentContext
from app.agent.planner import TaskPlanner
from app.agent.prompts import SYSTEM_PROMPT
from app.tools.registry import get_all_schemas
from app.tools import (
    list_files, read_file, write_file, edit_file,
    get_project_info, search_files, run_command, run_tests, git_status,
)
from app.security.sandbox import get_tool_risk, validate_command

logger = logging.getLogger("codepilot.agent")


class CodePilotAgent:
    def __init__(self, workspace: str):
        self.workspace = workspace
        self.context = AgentContext(SYSTEM_PROMPT)
        self.planner = TaskPlanner(llm_client, workspace)
        self._tool_schemas = get_all_schemas()

    def generate_plan(self, task: str) -> list[dict]:
        return self.planner.generate_plan(task)

    def add_user_message(self, content: str):
        self.context.add_user(content)

    def step(self) -> dict:
        """
        Single LLM step.
        Returns:
            {
              "type": "text" | "tool_calls" | "done",
              "content": str | None,
              "tool_calls": list,
              "finish_reason": str,
            }
        """
        result = llm_client.chat(
            messages=self.context.get_messages(),
            tools=self._tool_schemas,
            tool_choice="auto",
        )

        content = result.get("content")
        tool_calls = result.get("tool_calls", [])
        finish = result.get("finish_reason", "stop")

        # Record assistant turn in context
        self.context.add_assistant(content, tool_calls if tool_calls else None)

        if tool_calls:
            return {"type": "tool_calls", "content": content, "tool_calls": tool_calls, "finish_reason": finish}
        return {"type": "text", "content": content, "tool_calls": [], "finish_reason": finish}

    def execute_tool(self, tool_name: str, arguments: dict) -> dict:
        """
        Dispatch a tool call and return a structured result dict.
        """
        try:
            result = self._dispatch(tool_name, arguments)
        except Exception as exc:
            logger.error(f"Tool '{tool_name}' raised: {exc}", exc_info=True)
            result = {"error": str(exc), "success": False}

        return result

    def record_tool_result(self, tool_call_id: str, tool_name: str, result: dict):
        """Add tool result to context so the LLM can process it."""
        self.context.add_tool_result(tool_call_id, tool_name, json.dumps(result, default=str))

    def _dispatch(self, name: str, args: dict) -> dict:
        ws = self.workspace
        if name == "list_files":
            return list_files(ws, args.get("directory", ""), args.get("max_depth", 3))
        elif name == "read_file":
            return read_file(ws, args["path"])
        elif name == "write_file":
            return write_file(ws, args["path"], args["content"])
        elif name == "edit_file":
            return edit_file(ws, args["path"], args["old_string"], args["new_string"])
        elif name == "search_files":
            return search_files(
                ws, args["query"],
                directory=args.get("directory", ""),
                file_pattern=args.get("file_pattern", ""),
                case_sensitive=args.get("case_sensitive", False),
                max_results=args.get("max_results", 50),
            )
        elif name == "get_project_info":
            return get_project_info(ws)
        elif name == "run_command":
            return run_command(
                ws, args["command"],
                working_directory=args.get("working_directory", ""),
                timeout=args.get("timeout", None),
            )
        elif name == "run_tests":
            return run_tests(
                ws,
                test_path=args.get("test_path", ""),
                framework=args.get("framework", "auto"),
            )
        elif name == "git_status":
            return git_status(ws)
        else:
            return {"error": f"Unknown tool: {name}", "success": False}

    @staticmethod
    def get_tool_risk(tool_name: str) -> str:
        return get_tool_risk(tool_name)
