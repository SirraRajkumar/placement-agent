"""Offline unit tests for the Sheets-backed placement tools."""
from __future__ import annotations

import unittest
from datetime import date, timedelta
from unittest.mock import patch

from backend.sheets import SheetsStorage
from backend.tools.deadlines import check_deadlines
from backend.tools.logger import log_application
from backend.tools.errors import ToolError
from backend.tool_registry import _normalise_tool_input
from backend.agent import run_agent


class FakeWorksheet:
    def __init__(self, headers: list[str]) -> None:
        self.headers, self.rows = headers, []
    def row_values(self, _: int) -> list[str]: return self.headers
    def append_row(self, values: list[str]) -> None:
        if not self.headers:
            self.headers = list(values)
            return
        self.rows.append(dict(zip(self.headers, values)))
    def get_all_records(self, **_: object) -> list[dict[str, str]]: return self.rows.copy()
    def update(self, cell_range: str, values: list[list[str]]) -> None: self.rows[int(cell_range.split(":")[0][1:]) - 2] = dict(zip(self.headers, values[0]))


class FakeSpreadsheet:
    def __init__(self) -> None: self.sheets = {}
    def worksheet(self, name: str) -> FakeWorksheet: return self.sheets[name]
    def add_worksheet(self, title: str, rows: int, cols: int) -> FakeWorksheet:
        sheet = FakeWorksheet([]); self.sheets[title] = sheet; return sheet


class SheetsToolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.storage = SheetsStorage(FakeSpreadsheet())

    def test_create_update_and_no_duplicate_application(self) -> None:
        first = self.storage.upsert_application("Infosys", "Software Engineer", True, "2026-09-17", "Applied", "Campus")
        second = self.storage.upsert_application("Infosys", "Software Engineer", True, "2026-09-17", "Interview", None)
        self.assertEqual(first["application_id"], second["application_id"])
        self.assertEqual(len(self.storage.get_applications()), 1)
        self.assertEqual(second["notes"], "Campus")

    def test_deadline_filters(self) -> None:
        app = self.storage.upsert_application("Infosys", "Software Engineer", True, "2026-09-17", "Applied", None)
        self.storage.upsert_deadline(app, (date.today() + timedelta(days=3)).isoformat(), stage="Assessment")
        with patch("backend.tools.deadlines.get_storage", return_value=self.storage):
            result = check_deadlines(7, company="Infosys", role="Software Engineer", stage="Assessment")
        self.assertEqual(result["count"], 1)
        self.assertEqual(result["applications"][0]["company"], "Infosys")

    def test_logger_creates_linked_deadline(self) -> None:
        with patch("backend.tools.logger.get_storage", return_value=self.storage):
            result = log_application("Wipro", "Project Engineer", "Applied", "2026-09-17", "2026-10-03", deadline_stage="Assessment")
        self.assertEqual(result["application"]["company"], "Wipro")
        self.assertEqual(result["deadline"]["application_id"], result["application"]["application_id"])

    def test_announcement_can_save_deadline_without_marking_applied(self) -> None:
        with patch("backend.tools.logger.get_storage", return_value=self.storage):
            result = log_application(
                "Infosys", "Software Engineer", "Not Applied", deadline="2026-09-18",
                deadline_time="11:00 AM", deadline_stage="Application", applied=False,
            )
        self.assertEqual(result["application"]["applied"], "FALSE")
        self.assertEqual(result["application"]["applied_date"], "")
        self.assertEqual(result["deadline"]["stage"], "Application")
        self.assertEqual(result["deadline"]["deadline_time"], "11:00 AM")

    def test_relative_today_is_system_date(self) -> None:
        value = _normalise_tool_input("log_application", {"applied_date": "2020-01-01"}, user_message="I applied today", today=date(2026, 9, 17))
        self.assertEqual(value["applied_date"], "2026-09-17")

    def test_invalid_date_rejected(self) -> None:
        with self.assertRaises(ToolError):
            log_application("Wipro", "Engineer", "Applied", "17/09/2026")

    def test_greeting_does_not_call_a_tool(self) -> None:
        result = run_agent("Hello")
        self.assertEqual(result.tool_trace, [])
        self.assertIn("Hello", result.reply)


if __name__ == "__main__": unittest.main()
