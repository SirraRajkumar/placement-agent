"""Tool schemas and Python dispatch for the four supported tools."""

from __future__ import annotations

import re
from datetime import date, timedelta
from typing import Any, Callable

from backend.tools.deadlines import check_deadlines
from backend.tools.email_draft import draft_email
from backend.tools.logger import log_application
from backend.tools.research import research_company

TOOLS: list[dict[str, Any]] = [
    {
        "name": "check_deadlines",
        "description": "Read the application log and return active deadlines within the next N days.",
        "input_schema": {
            "type": "object",
            "properties": {
                "days_ahead": {
                    "type": "integer",
                    "description": (
                        "A whole-number integer from 0 to 90. "
                        "Use 14 for 'next 14 days', 7 for 'this week' or 'next 7 days'. "
                        "Pass the number itself, not text such as '14 days'."
                    ),
                },
                "company": {"type": "string", "description": "Optional stored company filter."},
                "role": {"type": "string", "description": "Optional stored role filter."},
                "stage": {"type": "string", "description": "Optional deadline stage filter such as Assessment."},
            },
            "required": ["days_ahead"],
        },
    },
    {
        "name": "research_company",
        "description": "Search the web for recent interview rounds, patterns, and preparation signals for a company and role.",
        "input_schema": {
            "type": "object",
            "properties": {
                "company_name": {"type": "string", "description": "Company to research."},
                "role": {"type": "string", "description": "Role if known; omit when unknown."},
            },
            "required": ["company_name"],
        },
    },
    {
        "name": "draft_email",
        "description": "Create an editable professional follow-up, thank-you, or application email.",
        "input_schema": {
            "type": "object",
            "properties": {
                "purpose": {
                    "type": "string",
                    "enum": ["follow_up", "thank_you", "application"],
                },
                "company": {"type": "string"},
                "role": {"type": "string"},
                "context": {"type": "string", "description": "Relevant timing or details supplied by the user."},
            },
            "required": ["purpose", "company", "role"],
        },
    },
    {
        "name": "log_application",
        "description": "Create or update the user's Google Sheets application/opportunity record. Dates must be ISO YYYY-MM-DD. If a deadline is supplied, save it as a linked deadline record.",
        "input_schema": {
            "type": "object",
            "properties": {
                "company": {"type": "string"},
                "role": {"type": "string"},
                "applied": {"type": "boolean", "description": "True only when the student explicitly says they applied or submitted. Use false for an announcement/opportunity."},
                "status": {
                    "type": "string",
                    "enum": ["Not Applied", "Applied", "Screening", "Interview", "Offer", "Rejected", "Withdrawn"],
                },
                "applied_date": {"type": "string", "description": "ISO date, YYYY-MM-DD. Required only when applied is true."},
                "deadline": {"type": "string", "description": "Optional ISO date, YYYY-MM-DD."},
                "deadline_time": {"type": "string", "description": "Optional deadline time exactly as supplied, for example 11:00 AM."},
                "deadline_stage": {"type": "string", "description": "Stage for an optional deadline: Application, Assessment, Interview, Document Verification, or Other."},
                "notes": {"type": "string"},
            },
            "required": ["company", "role", "status"],
        },
    },
]

# Ollama expects OpenAI-style function wrappers around the JSON schemas.
OLLAMA_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": tool["name"],
            "description": tool["description"],
            "parameters": tool["input_schema"],
        },
    }
    for tool in TOOLS
]

TOOL_FUNCTIONS: dict[str, Callable[..., dict[str, Any]]] = {
    "check_deadlines": check_deadlines,
    "research_company": research_company,
    "draft_email": draft_email,
    "log_application": log_application,
}


def execute_tool(name: str, tool_input: dict[str, Any], *, user_message: str | None = None) -> dict[str, Any]:
    """Execute a supported tool or raise a clear error for the agent to recover from."""
    if name not in TOOL_FUNCTIONS:
        raise ValueError(f"Unknown tool requested: {name}")
    return TOOL_FUNCTIONS[name](**_normalise_tool_input(name, tool_input, user_message=user_message))


def _resolve_relative_date(value: str, today: date) -> str | None:
    """Return an ISO date for the supported unambiguous relative-date phrases."""
    cleaned = value.strip().lower()
    if cleaned == "today":
        return today.isoformat()
    if cleaned == "yesterday":
        return (today - timedelta(days=1)).isoformat()
    if cleaned == "tomorrow":
        return (today + timedelta(days=1)).isoformat()
    if cleaned == "next week":
        days_until_next_monday = 7 - today.weekday()
        return (today + timedelta(days=days_until_next_monday)).isoformat()
    match = re.fullmatch(r"next\s+(monday|tuesday|wednesday|thursday|friday|saturday|sunday)", cleaned)
    if match:
        weekdays = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6}
        days_ahead = (weekdays[match.group(1)] - today.weekday()) % 7 or 7
        return (today + timedelta(days=days_ahead)).isoformat()
    return None


def _relative_date_mentioned_for(field: str, user_message: str, today: date) -> str | None:
    """Find a relative date attached to an application or deadline in user text."""
    phrase = r"today|yesterday|tomorrow|next\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|week)"
    subject = r"(?:applied|application)" if field == "applied_date" else r"(?:deadline|due date|due)"
    match = re.search(rf"\b{subject}\b[^.!?]{{0,120}}?\b({phrase})\b", user_message, flags=re.IGNORECASE)
    return _resolve_relative_date(match.group(1), today) if match else None


def _normalise_tool_input(
    name: str, tool_input: dict[str, Any], *, user_message: str | None = None, today: date | None = None
) -> dict[str, Any]:
    """Repair safe type variations returned by local model tool calls.

    Ollama models occasionally serialize JSON-schema integers as strings.  This
    is limited to supported fields. In addition to deadline-window integers,
    it resolves supported relative application dates against the actual system
    date, never a model-supplied calendar date.
    """
    normalised = dict(tool_input)
    if name == "check_deadlines" and "days_ahead" in normalised:
        value = normalised["days_ahead"]
        if isinstance(value, str):
            cleaned = value.strip().lower()
            if cleaned in {"this week", "next week"}:
                normalised["days_ahead"] = 7
            elif re.fullmatch(r"\d+", cleaned):
                normalised["days_ahead"] = int(cleaned)
            else:
                match = re.fullmatch(r"(?:next\s+)?(\d+)\s+days?", cleaned)
                if match:
                    normalised["days_ahead"] = int(match.group(1))

    if name == "log_application":
        reference_date = today or date.today()
        for field in ("applied_date", "deadline"):
            value = normalised.get(field)
            resolved = _resolve_relative_date(value, reference_date) if isinstance(value, str) else None
            if user_message:
                resolved = _relative_date_mentioned_for(field, user_message, reference_date) or resolved
            if resolved:
                normalised[field] = resolved
    return normalised
