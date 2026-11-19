"""
LLM client — wraps the OpenAI SDK.
Supports any OpenAI-compatible provider via OPENAI_BASE_URL:
  - Groq:       base_url=https://api.groq.com/openai/v1
  - OpenRouter: base_url=https://openrouter.ai/api/v1
  - Ollama:     base_url=http://localhost:11434/v1
  - OpenAI:     base_url=  (empty → default)
"""
import json
import logging
from typing import Optional
from openai import OpenAI, APIConnectionError, AuthenticationError, RateLimitError, APIStatusError

from app.config import settings

logger = logging.getLogger("codepilot.llm")


class LLMClient:
    def __init__(self):
        self._client: Optional[OpenAI] = None

    def _get_client(self) -> OpenAI:
        """Lazy init — reset _client to None to force reconnect with new creds."""
        if self._client is None:
            kwargs: dict = {"api_key": settings.OPENAI_API_KEY}
            if settings.OPENAI_BASE_URL:
                kwargs["base_url"] = settings.OPENAI_BASE_URL
            self._client = OpenAI(**kwargs)
            provider = settings.OPENAI_BASE_URL or "api.openai.com"
            logger.info(f"LLM client connected to {provider} model={settings.OPENAI_MODEL}")
        return self._client

    def chat(
        self,
        messages: list[dict],
        tools: Optional[list[dict]] = None,
        tool_choice: str = "auto",
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        stream: bool = False,
    ) -> dict:
        """
        Send a chat completion request.
        Returns:
          {"content": str|None, "tool_calls": [...], "finish_reason": str, "usage": {...}}
        """
        client = self._get_client()
        kwargs: dict = {
            "model": settings.OPENAI_MODEL,
            "messages": messages,
            "temperature": temperature if temperature is not None else settings.OPENAI_TEMPERATURE,
            "max_tokens": max_tokens if max_tokens is not None else settings.OPENAI_MAX_TOKENS,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice

        try:
            response = client.chat.completions.create(**kwargs)
        except AuthenticationError as exc:
            raise ValueError(
                f"Authentication failed — check your API key for provider: "
                f"{settings.OPENAI_BASE_URL or 'OpenAI'}. Error: {exc}"
            ) from exc
        except RateLimitError as exc:
            raise ValueError(
                "Rate limit reached. Please wait and try again."
            ) from exc
        except APIConnectionError as exc:
            raise ConnectionError(
                f"Cannot connect to {settings.OPENAI_BASE_URL or 'api.openai.com'}: {exc}"
            ) from exc
        except APIStatusError as exc:
            raise ValueError(
                f"API error {exc.status_code}: {exc.message}"
            ) from exc

        choice = response.choices[0]
        msg = choice.message

        tool_calls = []
        if msg.tool_calls:
            for tc in msg.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError:
                    args = {"raw": tc.function.arguments}
                tool_calls.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": args,
                })

        usage = {}
        if response.usage:
            usage = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
            }

        return {
            "content": msg.content,
            "tool_calls": tool_calls,
            "finish_reason": choice.finish_reason,
            "usage": usage,
        }

    def simple_chat(self, messages: list[dict], max_tokens: int = 2048) -> str:
        """Convenience method — returns just the text content."""
        result = self.chat(messages, max_tokens=max_tokens)
        return result.get("content") or ""

    async def test_connection(self) -> bool:
        import asyncio
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._test_sync)

    def _test_sync(self) -> bool:
        """Send a minimal request — just check that the API responds without error."""
        result = self.chat(
            messages=[{"role": "user", "content": "Reply with the single word: OK"}],
            max_tokens=10,
        )
        # Accept any non-error response (some models return empty string for trivial prompts)
        return result.get("finish_reason") in ("stop", "end_turn", "length", "eos_token") or bool(result.get("content"))


llm_client = LLMClient()
