"""LLM-backed email drafting tool."""

from __future__ import annotations

from backend.config import LLM_PROVIDER, OLLAMA_MODEL
from backend.tools.errors import ToolError

VALID_PURPOSES = {"follow_up", "thank_you", "application"}


def draft_email(
    purpose: str, company: str, role: str, context: str | None = None
) -> dict[str, str]:
    """Draft a concise, editable professional email using a dedicated LLM call."""
    purpose = purpose.strip().lower()
    company = company.strip()
    role = role.strip()
    if purpose not in VALID_PURPOSES:
        raise ToolError("purpose must be follow_up, thank_you, or application.")
    if not company or not role:
        raise ToolError("company and role are required to draft an email.")
    if LLM_PROVIDER != "ollama":
        raise ToolError("LLM_PROVIDER must be set to ollama for email drafting.")

    instructions = {
        "follow_up": "Write a polite follow-up after an application without sounding demanding.",
        "thank_you": "Write a warm, succinct thank-you after an interview or recruiter conversation.",
        "application": "Write a concise application email that expresses fit without inventing qualifications.",
    }[purpose]
    prompt = f"""{instructions}

Company: {company}
Role: {role}
Additional context: {context or 'None provided'}

Return only a ready-to-edit plain-text email beginning with these placeholders:
To: [Recruiter email]
From: [Your email]
Subject: ...

Then include a greeting, body, closing, and [Your Name] placeholder. Do not
claim facts not supplied. Do not send the email or invent contact details."""
    try:
        import ollama

        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": "You write precise, professional placement-season emails for students."},
                {"role": "user", "content": prompt},
            ],
        )
        draft = (response.message.content or "").strip()
    except ModuleNotFoundError as exc:
        raise ToolError("Ollama is not installed. Run pip install -r requirements.txt.") from exc
    except Exception as exc:
        raise ToolError(f"Email drafting through Ollama failed: {exc}") from exc

    if not draft:
        raise ToolError("Ollama returned an empty email draft. Please try again.")
    return {"purpose": purpose, "company": company, "role": role, "draft": draft}
