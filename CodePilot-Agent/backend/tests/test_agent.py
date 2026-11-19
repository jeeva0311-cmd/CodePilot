"""
Agent unit tests — mock the LLM client so no real API calls are made.
"""
import json
import pytest
from unittest.mock import MagicMock, patch


def _mock_llm_response(content=None, tool_calls=None, finish_reason="stop"):
    return {
        "content": content,
        "tool_calls": tool_calls or [],
        "finish_reason": finish_reason,
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }


def test_agent_context_adds_messages():
    from app.agent.context import AgentContext
    ctx = AgentContext("System prompt")
    ctx.add_user("Hello")
    ctx.add_assistant("Hi!")
    msgs = ctx.get_messages()
    assert msgs[0]["role"] == "system"
    assert msgs[1]["role"] == "user"
    assert msgs[2]["role"] == "assistant"


def test_agent_context_truncates_long_tool_result():
    from app.agent.context import AgentContext
    ctx = AgentContext("System")
    ctx.add_tool_result("tc1", "read_file", "x" * 10000)
    msgs = ctx.get_messages()
    tool_msg = next(m for m in msgs if m["role"] == "tool")
    assert len(tool_msg["content"]) <= 8010


def test_planner_fallback(tmp_path):
    from app.agent.planner import TaskPlanner
    mock_llm = MagicMock()
    mock_llm.chat.side_effect = Exception("API error")
    planner = TaskPlanner(mock_llm, str(tmp_path))
    plan = planner.generate_plan("Build something")
    assert len(plan) > 0
    assert plan[0]["status"] == "pending"


def test_planner_generates_plan(tmp_path):
    from app.agent.planner import TaskPlanner
    mock_llm = MagicMock()
    mock_llm.chat.return_value = _mock_llm_response(
        content='[{"description": "Step 1", "status": "pending"}, {"description": "Step 2", "status": "pending"}]'
    )
    planner = TaskPlanner(mock_llm, str(tmp_path))
    plan = planner.generate_plan("Do something")
    assert len(plan) == 2
    assert plan[0]["description"] == "Step 1"


def test_planner_advance(tmp_path):
    from app.agent.planner import TaskPlanner
    mock_llm = MagicMock()
    mock_llm.chat.return_value = _mock_llm_response(
        content='[{"description":"A","status":"pending"},{"description":"B","status":"pending"}]'
    )
    planner = TaskPlanner(mock_llm, str(tmp_path))
    planner.generate_plan("task")
    planner.start_first()
    assert planner.steps[0]["status"] == "in_progress"
    planner.advance()
    assert planner.steps[0]["status"] == "completed"
    assert planner.steps[1]["status"] == "in_progress"


def test_agent_dispatches_list_files(tmp_path):
    from app.agent.agent import CodePilotAgent
    agent = CodePilotAgent(str(tmp_path))
    result = agent.execute_tool("list_files", {})
    assert "tree" in result


def test_agent_dispatches_unknown_tool(tmp_path):
    from app.agent.agent import CodePilotAgent
    agent = CodePilotAgent(str(tmp_path))
    result = agent.execute_tool("unknown_tool_xyz", {})
    assert "error" in result


def test_agent_step_text_response(tmp_path):
    from app.agent.agent import CodePilotAgent
    agent = CodePilotAgent(str(tmp_path))
    agent.context.add_user("hello")

    with patch("app.agent.agent.llm_client") as mock_llm:
        mock_llm.chat.return_value = _mock_llm_response(content="Hello! How can I help?")
        result = agent.step()

    assert result["type"] == "text"
    assert result["content"] == "Hello! How can I help?"


def test_agent_step_tool_call(tmp_path):
    from app.agent.agent import CodePilotAgent
    agent = CodePilotAgent(str(tmp_path))
    agent.context.add_user("list files")

    with patch("app.agent.agent.llm_client") as mock_llm:
        mock_llm.chat.return_value = _mock_llm_response(
            tool_calls=[{"id": "tc1", "name": "list_files", "arguments": {}}],
            finish_reason="tool_calls",
        )
        result = agent.step()

    assert result["type"] == "tool_calls"
    assert result["tool_calls"][0]["name"] == "list_files"


def test_cancel_flag():
    from app.agent.loop import cancel_task, _is_cancelled, _cancel_flags
    task_id = "test-cancel-999"
    assert _is_cancelled(task_id) is False
    cancel_task(task_id)
    assert _is_cancelled(task_id) is True
    _cancel_flags.pop(task_id, None)
