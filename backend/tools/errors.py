"""Shared, safe error type for user-facing tool failures."""


class ToolError(ValueError):
    """An expected tool error that the model can recover from conversationally."""
