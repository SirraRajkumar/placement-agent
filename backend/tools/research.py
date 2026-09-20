"""Company interview-process research tool powered by Tavily."""

from __future__ import annotations

import os
from typing import Any

from backend.config import TAVILY_MAX_RESULTS
from backend.tools.errors import ToolError


def research_company(company_name: str, role: str | None = None) -> dict[str, Any]:
    """Search recent, attributable interview-process reports for a company.

    Raw snippets are deliberately returned to the orchestrator rather than
    summarised in a second LLM call.  It keeps the agent's reasoning and final
    answer in one traceable model conversation and avoids an unnecessary call.
    """
    company_name = company_name.strip()
    if not company_name:
        raise ToolError("company_name is required for company research.")
    api_key = os.getenv("TAVILY_API_KEY")
    if not api_key:
        raise ToolError("TAVILY_API_KEY is not configured, so company research is unavailable.")

    try:
        from tavily import TavilyClient
    except ImportError as exc:
        raise ToolError("Tavily is not installed. Run pip install -r requirements.txt.") from exc

    role_clause = f" {role.strip()}" if role and role.strip() else " fresher"
    query = f"{company_name}{role_clause} interview process rounds experience India"
    try:
        response = TavilyClient(api_key=api_key).search(
            query=query,
            max_results=TAVILY_MAX_RESULTS,
            search_depth="basic",
        )
    except Exception as exc:  # Provider failures should reach the agent as tool results.
        raise ToolError(f"Company research search failed: {exc}") from exc

    sources = [
        {
            "title": item.get("title", "Untitled result"),
            "url": item.get("url", ""),
            "snippet": item.get("content", "")[:800],
        }
        for item in response.get("results", [])
        if item.get("content")
    ]
    if not sources:
        raise ToolError(f"No useful interview-process results were found for {company_name}.")
    return {"company": company_name, "role": role, "query": query, "sources": sources}
