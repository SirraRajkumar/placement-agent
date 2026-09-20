"""Google Sheets storage layer - the placement tracker's single source of truth."""

from __future__ import annotations

import os
from datetime import date
from pathlib import Path
from typing import Any

from backend.config import load_dotenv

load_dotenv()

APPLICATION_HEADERS = ["application_id", "company", "role", "applied", "applied_date", "status", "notes", "updated_at"]
DEADLINE_HEADERS = ["deadline_id", "application_id", "company", "role", "stage", "deadline_date", "deadline_time", "status", "source", "notes"]


class SheetsError(RuntimeError):
    """A safe, user-facing Google Sheets storage error."""


def _clean(record: dict[str, Any], headers: list[str]) -> dict[str, str]:
    return {header: str(record.get(header) or "").strip() for header in headers}


class SheetsStorage:
    """The only component that reads and writes the placement spreadsheet."""

    def __init__(self, spreadsheet: Any | None = None) -> None:
        self._spreadsheet = spreadsheet

    def _connect(self) -> Any:
        if self._spreadsheet is not None:
            return self._spreadsheet
        sheet_id, credentials_file = os.getenv("GOOGLE_SHEET_ID"), os.getenv("GOOGLE_CREDENTIALS_FILE")
        if not sheet_id or not credentials_file:
            raise SheetsError("Google Sheets is not configured. Set GOOGLE_SHEET_ID and GOOGLE_CREDENTIALS_FILE in .env.")
        if not Path(credentials_file).is_file():
            raise SheetsError("The configured Google service-account credentials file was not found.")
        try:
            import gspread
            from google.oauth2.service_account import Credentials
            credentials = Credentials.from_service_account_file(credentials_file, scopes=["https://www.googleapis.com/auth/spreadsheets"])
            self._spreadsheet = gspread.authorize(credentials).open_by_key(sheet_id)
            return self._spreadsheet
        except Exception as exc:
            raise SheetsError("Could not connect to the placement Google Sheet. Check sharing and service-account settings.") from exc

    def _worksheet(self, name: str, headers: list[str]) -> Any:
        spreadsheet = self._connect()
        try:
            worksheet = spreadsheet.worksheet(name)
        except Exception:
            try:
                worksheet = spreadsheet.add_worksheet(title=name, rows=1000, cols=len(headers))
                worksheet.append_row(headers)
            except Exception as exc:
                raise SheetsError(f"Could not access or create the {name} worksheet.") from exc
        existing = worksheet.row_values(1)
        if not existing:
            worksheet.append_row(headers)
        elif existing[:len(headers)] != headers:
            raise SheetsError(f"The {name} worksheet must have these columns: {', '.join(headers)}.")
        return worksheet

    @staticmethod
    def _records(worksheet: Any, headers: list[str]) -> list[dict[str, str]]:
        return [_clean(row, headers) for row in worksheet.get_all_records(expected_headers=headers)]

    @staticmethod
    def _next_id(prefix: str, records: list[dict[str, str]], key: str) -> str:
        ids = [int(record[key][len(prefix):]) for record in records if record.get(key, "").startswith(prefix) and record[key][len(prefix):].isdigit()]
        return f"{prefix}{(max(ids) if ids else 0) + 1:03d}"

    def get_applications(self) -> list[dict[str, str]]:
        return self._records(self._worksheet("Applications", APPLICATION_HEADERS), APPLICATION_HEADERS)

    def upsert_application(self, company: str, role: str, applied: bool, applied_date: str | None, status: str, notes: str | None) -> dict[str, str]:
        worksheet = self._worksheet("Applications", APPLICATION_HEADERS)
        records = self._records(worksheet, APPLICATION_HEADERS)
        index = next((i for i, row in enumerate(records) if row["company"].casefold() == company.casefold() and row["role"].casefold() == role.casefold()), None)
        old = records[index] if index is not None else {}
        record = {"application_id": old.get("application_id") or self._next_id("APP", records, "application_id"), "company": company, "role": role, "applied": "TRUE" if applied else old.get("applied", "FALSE"), "applied_date": applied_date or old.get("applied_date", ""), "status": status or old.get("status", "Not Applied"), "notes": notes if notes is not None else old.get("notes", ""), "updated_at": date.today().isoformat()}
        values = [record[key] for key in APPLICATION_HEADERS]
        if index is None:
            worksheet.append_row(values)
        else:
            worksheet.update(f"A{index + 2}:H{index + 2}", [values])
        return record

    def get_deadlines(self, *, company: str | None = None, role: str | None = None, stage: str | None = None) -> list[dict[str, str]]:
        records = self._records(self._worksheet("Deadlines", DEADLINE_HEADERS), DEADLINE_HEADERS)
        return [row for row in records if all(value is None or row[field].casefold() == value.casefold() for field, value in (("company", company), ("role", role), ("stage", stage)))]

    def upsert_deadline(self, application: dict[str, str], deadline_date: str, *, stage: str = "Other", deadline_time: str | None = None, notes: str | None = None) -> dict[str, str]:
        worksheet = self._worksheet("Deadlines", DEADLINE_HEADERS)
        records = self._records(worksheet, DEADLINE_HEADERS)
        index = next((i for i, row in enumerate(records) if row["application_id"] == application["application_id"] and row["stage"].casefold() == stage.casefold()), None)
        old = records[index] if index is not None else {}
        record = {"deadline_id": old.get("deadline_id") or self._next_id("DL", records, "deadline_id"), "application_id": application["application_id"], "company": application["company"], "role": application["role"], "stage": stage, "deadline_date": deadline_date, "deadline_time": deadline_time or old.get("deadline_time", ""), "status": old.get("status", "Active") or "Active", "source": old.get("source", "User") or "User", "notes": notes if notes is not None else old.get("notes", "")}
        values = [record[key] for key in DEADLINE_HEADERS]
        if index is None:
            worksheet.append_row(values)
        else:
            worksheet.update(f"A{index + 2}:J{index + 2}", [values])
        return record


_storage: SheetsStorage | None = None


def get_storage() -> SheetsStorage:
    global _storage
    if _storage is None:
        _storage = SheetsStorage()
    return _storage
