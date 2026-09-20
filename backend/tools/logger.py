"""Application logger backed by the Google Sheets storage layer."""
from __future__ import annotations

from datetime import date
from typing import Any

from backend.sheets import SheetsError, get_storage
from backend.tools.errors import ToolError

ALLOWED_STATUSES = {"Not Applied", "Applied", "Screening", "Interview", "Offer", "Rejected", "Withdrawn"}


def _iso(value: str | None, field: str, required: bool = False) -> str | None:
    if not value:
        if required:
            raise ToolError(f"{field} is required and must use YYYY-MM-DD format.")
        return None
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise ToolError(f"{field} must use YYYY-MM-DD format.") from exc


def log_application(
    company: str,
    role: str,
    status: str,
    applied_date: str | None = None,
    deadline: str | None = None,
    deadline_time: str | None = None,
    notes: str | None = None,
    deadline_stage: str = "Other",
    applied: bool = True,
) -> dict[str, Any]:
    """Upsert an application and, when supplied, its linked deadline."""
    company, role, status = company.strip(), role.strip(), status.strip().title()
    if not company or not role:
        raise ToolError("Both company and role are required to log an application.")
    if status not in ALLOWED_STATUSES:
        raise ToolError(f"status must be one of: {', '.join(sorted(ALLOWED_STATUSES))}.")
    if not isinstance(applied, bool):
        raise ToolError("applied must be true or false.")
    if applied and not applied_date:
        raise ToolError("applied_date is required when applied is true and must use YYYY-MM-DD format.")
    try:
        application = get_storage().upsert_application(company, role, applied, _iso(applied_date, "applied_date", applied), status, notes)
        saved_deadline = (
            get_storage().upsert_deadline(
                application, _iso(deadline, "deadline", True), stage=deadline_stage,
                deadline_time=deadline_time, notes=notes,
            )
            if deadline else None
        )
    except SheetsError as exc:
        raise ToolError(str(exc)) from exc
    return {"action": "saved", "application": application, "deadline": saved_deadline}
