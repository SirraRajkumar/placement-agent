"""Explicit Ollama function-calling loop for the Placement Assistant."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from backend.config import LLM_PROVIDER, OLLAMA_MODEL
from backend.system_prompt import build_system_prompt
from backend.tool_registry import OLLAMA_TOOLS, _normalise_tool_input, execute_tool
from backend.tools.errors import ToolError

MAX_TOOL_ROUNDS = 8


class AgentConfigurationError(RuntimeError):
    """Raised when a required local configuration value is not available."""


@dataclass
class AgentResult:
    reply: str
    tool_trace: list[dict[str, Any]]


def _history_messages(history: list[dict[str, str]] | None) -> list[dict[str, Any]]:
    """Accept only ordinary user/assistant text turns from the client."""
    messages: list[dict[str, Any]] = []
    for item in history or []:
        role = item.get("role")
        content = item.get("content", "").strip()
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": content})
    return messages


def _casual_reply(message: str) -> str | None:
    """Avoid a small local model selecting a data tool for an ordinary greeting."""
    cleaned = message.strip().casefold()
    if re.fullmatch(r"(?:hi|hello|hey|hii+|good\s+(?:morning|afternoon|evening))[!,.\s]*", cleaned):
        return (
            "Hello! I can help you track placement applications and deadlines, "
            "research interview processes, draft emails, or review a resume/job description."
        )
    return None


def _ollama_assistant_message(message: Any, tool_calls: list[Any]) -> dict[str, Any]:
    """Convert Ollama's response object into the next conversation message."""
    result: dict[str, Any] = {"role": "assistant", "content": message.content or ""}
    if tool_calls:
        result["tool_calls"] = [
            {
                "type": "function",
                "function": {
                    "name": call.function.name,
                    "arguments": dict(call.function.arguments),
                },
            }
            for call in tool_calls
        ]
    return result


def run_agent(
    user_message: str,
    history: list[dict[str, str]] | None = None,
    *,
    client: Any | None = None,
) -> AgentResult:
    """Run the transparent Ollama model -> tool -> model loop until it returns text.

    Each tool result is appended as an Ollama `role: tool` message. This gives
    the local model its observation before it decides if another action is
    needed, which is what enables multi-tool chains.
    """
    if not user_message or not user_message.strip():
        raise ValueError("message cannot be empty")
    casual_reply = _casual_reply(user_message)
    if casual_reply:
        return AgentResult(reply=casual_reply, tool_trace=[])
    if LLM_PROVIDER != "ollama":
        raise AgentConfigurationError("LLM_PROVIDER must be set to ollama.")
    if client is None:
        try:
            import ollama
        except ModuleNotFoundError as exc:
            raise AgentConfigurationError("Ollama is not installed. Run pip install -r requirements.txt.") from exc
        client = ollama.Client()
    messages = [{"role": "system", "content": build_system_prompt()}]
    messages.extend(_history_messages(history))
    messages.append({"role": "user", "content": user_message.strip()})
    trace: list[dict[str, Any]] = []

    for _round in range(MAX_TOOL_ROUNDS):
        try:
            response = client.chat(model=OLLAMA_MODEL, messages=messages, tools=OLLAMA_TOOLS)
        except Exception as exc:
            raise AgentConfigurationError(
                f"Could not reach Ollama or load {OLLAMA_MODEL!r}. Start Ollama and run `ollama pull {OLLAMA_MODEL}`."
            ) from exc

        assistant_message = response.message
        tool_uses = list(assistant_message.tool_calls or [])
        if not tool_uses:
            return AgentResult(reply=(assistant_message.content or "").strip(), tool_trace=trace)

        # Preserve Ollama's exact tool calls before giving it each tool result.
        messages.append(_ollama_assistant_message(assistant_message, tool_uses))
        for tool_use in tool_uses:
            tool_name = tool_use.function.name
            tool_input = dict(tool_use.function.arguments)
            normalised_input = _normalise_tool_input(tool_name, tool_input, user_message=user_message)
            try:
                result = execute_tool(tool_name, normalised_input, user_message=user_message)
                trace.append({"tool": tool_name, "input": normalised_input, "ok": True})
                result_text = json.dumps(result, default=str)
            except (ToolError, ValueError, TypeError) as exc:
                trace.append({"tool": tool_name, "input": normalised_input, "ok": False, "error": str(exc)})
                result_text = json.dumps({"error": str(exc)})
            except Exception:
                # Keep implementation internals out of the user/model transcript.
                message = "The tool encountered an unexpected error. Ask the user to try again or choose another action."
                trace.append({"tool": tool_name, "input": normalised_input, "ok": False, "error": message})
                result_text = json.dumps({"error": message})
            messages.append(
                {
                    "role": "tool",
                    "tool_name": tool_name,
                    "content": result_text,
                }
            )

    return AgentResult(
        reply="I stopped after several tool steps to avoid a loop. Please try a more specific request.",
        tool_trace=trace,
    )
