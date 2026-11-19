"""
Agent context manager — maintains the message history sent to the LLM.
Keeps token count manageable by trimming old tool results when necessary.
"""
from typing import Optional


class AgentContext:
    def __init__(self, system_prompt: str, max_messages: int = 60):
        self._system_prompt = system_prompt
        self._max_messages = max_messages
        self._messages: list[dict] = []

    def add_user(self, content: str):
        self._messages.append({"role": "user", "content": content})

    def add_assistant(self, content: Optional[str], tool_calls: Optional[list] = None):
        msg: dict = {"role": "assistant"}
        if content:
            msg["content"] = content
        if tool_calls:
            # OpenAI format for tool call messages
            msg["tool_calls"] = [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": __import__("json").dumps(tc["arguments"]),
                    },
                }
                for tc in tool_calls
            ]
        if "content" not in msg:
            msg["content"] = None
        self._messages.append(msg)

    def add_tool_result(self, tool_call_id: str, tool_name: str, content: str):
        # Truncate very long tool results to avoid blowing the context window
        if len(content) > 8000:
            content = content[:7800] + "\n… [output truncated] …"
        self._messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "name": tool_name,
            "content": content,
        })

    def get_messages(self) -> list[dict]:
        """Return messages in OpenAI format, with the system prompt prepended."""
        msgs = [{"role": "system", "content": self._system_prompt}]
        # Trim if too many messages (keep last _max_messages)
        history = self._messages[-self._max_messages:]
        msgs.extend(history)
        return msgs

    def message_count(self) -> int:
        return len(self._messages)

    def clear(self):
        self._messages = []
