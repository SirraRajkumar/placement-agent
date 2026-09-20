"""Deadline tracker backed by the Google Sheets storage layer."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from backend.sheets import SheetsError, get_storage
from backend.tools.errors import ToolError


def check_deadlines(days_ahead: int = 7, company: str | None = None, role: str | None = None, stage: str | None = None) -> dict[str, Any]:
    """Read personal placement deadlines from Google Sheets, never web search."""
    if isinstance(days_ahead, bool) or not isinstance(days_ahead, int) or not 0 <= days_ahead <= 90:
        raise ToolError("days_ahead must be a whole number from 0 to 90.")
    today, end_date = date.today(), date.today() + timedelta(days=days_ahead)
    try:
        records = get_storage().get_deadlines(company=company, role=role, stage=stage)
    except SheetsError as exc:
        raise ToolError(str(exc)) from exc
    matches = []
    for record in records:
        try:
            due = date.fromisoformat(record["deadline_date"])
        except ValueError:
            continue
        if record["status"] in {"Completed", "Missed", "Cancelled"} or not today <= due <= end_date:
            continue
        matches.append({**record, "days_until_deadline": (due - today).days})
    matches.sort(key=lambda record: record["deadline_date"])
    return {"window_start": today.isoformat(), "window_end": end_date.isoformat(), "days_ahead": days_ahead, "count": len(matches), "applications": matches}
