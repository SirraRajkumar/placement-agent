# Placement Assistant Agent

A local, tool-using campus-placement assistant. It chats through Ollama, uses Google Sheets as the single source of truth for personal placement records, uses Tavily only for current company research, and creates editable email drafts without sending mail.

## Architecture

```text
User → Streamlit → FastAPI → Ollama agent → Python tool → Storage layer → Google Sheets
                                                ├── Tavily (company research)
                                                └── Ollama (email drafts)
```

The agent in `backend/agent.py` decides which of the four tools to call. Tools never contain raw Google API calls; `backend/sheets.py` is the only Sheets storage boundary. This prevents the model from inventing or directly modifying personal placement data.

## Tools

- `check_deadlines`: reads active personal deadlines from Google Sheets, with optional company, role, and stage filters.
- `research_company`: retrieves recent interview-process reports from Tavily. These are web sources, not personal tracker data.
- `draft_email`: creates an editable follow-up, thank-you, or application email locally with Ollama. It never sends an email.
- `log_application`: creates or updates an application/opportunity and optionally its linked deadline.

The agent resolves relative dates such as `today`, `tomorrow`, and `next Monday` against the real system date. An announcement is stored as `Not Applied` only when it has sufficient structured details; it never implies the student applied.

## Google Sheets tracker

Create one spreadsheet and share it with the service-account email as an **Editor**. The app creates these tabs and header rows automatically if they do not already exist.

`Applications` columns:

```text
application_id, company, role, applied, applied_date, status, notes, updated_at
```

`Deadlines` columns:

```text
deadline_id, application_id, company, role, stage, deadline_date,
deadline_time, status, source, notes
```

Application identity is `company + role`, so logging the same application later updates it instead of creating a duplicate. Deadline rows retain their own IDs and link to the application ID. Google Sheets—not SQLite—is the only active persistent tracker.

## Setup

1. Use Python 3.11+ and create a virtual environment.

   ```powershell
   py -3.11 -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -r requirements.txt
   ```

2. Install Ollama and pull the configured models.

   ```powershell
   ollama pull llama3.2:3b
   ollama pull llama3.2-vision:11b
   ```

   You may instead set `OLLAMA_MODEL=gpt-oss:20b` after pulling that model. The vision model is only required for image attachments; PDFs are read locally.

3. In Google Cloud, enable the Google Sheets API, create a service account, download its JSON key to `credentials/service_account.json`, and share the placement spreadsheet with the service account's email address.

4. Copy `.env.example` to `.env` and set its values:

   ```dotenv
   LLM_PROVIDER=ollama
   OLLAMA_MODEL=llama3.2:3b
   OLLAMA_VISION_MODEL=llama3.2-vision:11b
   TAVILY_API_KEY=your_tavily_api_key
   TAVILY_MAX_RESULTS=5
   GOOGLE_SHEET_ID=your_google_sheet_id
   GOOGLE_CREDENTIALS_FILE=credentials/service_account.json
   PLACEMENT_API_URL=http://127.0.0.1:8000
   ```

   Tavily is optional unless company research is used. Ollama is local and does not need an API key.

5. Run the backend and frontend in separate terminals.

   ```powershell
   uvicorn backend.main:app --reload
   streamlit run frontend/app.py
   ```

Open `http://127.0.0.1:8501`. `GET /health`, `GET /applications`, `GET /deadlines`, and `POST /chat` are available from FastAPI.

## Example conversations

- “Any deadlines coming up this week?” — reads the Google Sheets deadlines.
- “What is TCS's interview process like?” — uses Tavily research and returns sourced, non-guaranteed reports.
- “Draft a follow-up email to the Infosys recruiter. It has been two weeks.” — returns a draft with address placeholders; it does not send it.
- “I just applied to Wipro for Project Engineer today.” — upserts the Sheets application with the actual date.
- “I applied to Wipro for Project Engineer today. The assessment deadline is October 3.” — updates the application and creates/updates a linked assessment deadline.
- Paste a resume or job description PDF/image and ask for role-fit, resume improvements, or interview preparation.

If the role is missing from an application report, the assistant asks for it rather than writing an incomplete record. If no personal deadline exists, it reports that no tracker record exists; it does not search the web to fabricate one.

## Tests

Run the offline tests (they use a fake Sheets client, not your real spreadsheet):

```powershell
python -m unittest discover -s tests -v
```

They cover application creation/update and duplicate prevention, linked deadlines, deadline filters, invalid dates, relative dates, and announcement records that are not applications.

## Security

`.env` and `credentials/` are ignored by Git. Never commit the Google service-account JSON, the Google Sheet ID if it is sensitive, or Tavily keys. The frontend only talks to FastAPI and never receives credentials. There is no Gmail API or email sending in this project.
