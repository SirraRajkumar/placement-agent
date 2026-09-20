"""Compatibility exports for the four Placement Assistant tools.

New application code should import from ``backend.tools`` or
``backend.tool_registry`` directly.
"""

from backend.tools.deadlines import check_deadlines
from backend.tools.email_draft import draft_email
from backend.tools.logger import log_application
from backend.tools.research import research_company

__all__ = ["check_deadlines", "draft_email", "log_application", "research_company"]
