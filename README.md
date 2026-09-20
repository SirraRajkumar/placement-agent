# Placement Assistant Agent

A local, tool-using campus-placement assistant that helps students track applications and deadlines, research companies, prepare emails, and analyze resumes or job descriptions.

The application uses **Ollama for local LLM inference**, **Google Sheets as the single source of truth for personal placement records**, and **Tavily only for current company research**. Email drafts are generated locally and are never sent automatically.

## Features

* 📋 **Application tracking** — create and update placement applications in Google Sheets.
* ⏰ **Deadline tracking** — check upcoming placement deadlines with optional company, role, and stage filters.
* 🔎 **Company research** — retrieve recent interview-process reports using Tavily.
* ✉️ **Email drafting** — generate editable follow-up, thank-you, or application emails without sending them.
* 📄 **Resume and job-description analysis** — analyze uploaded PDF/image documents for role fit, resume improvements, and interview preparation.
* 📅 **Relative date handling** — understands dates such as `today`, `tomorrow`, and `next Monday`.
* 🔒 **Local-first architecture** — Ollama handles LLM inference locally; personal placement records remain in Google Sheets.

## Architecture

```text
User
  │
  ▼
Streamlit Frontend
  │
  ▼
FastAPI Backend
  │
  ▼
Ollama Agent
  │
  ├── check_deadlines ────────► Google Sheets
  │
  ├── log_application ────────► Google Sheets
  │
  ├── research_company ───────► Tavily
  │
  └── draft_email ────────────► Ollama
```

The agent in `backend/agent.py` decides which tool to call.

Tools do not contain raw Google API calls. `backend/sheets.py` is the only Google Sheets storage boundary. This keeps personal placement data behind a controlled storage layer and prevents the model from directly inventing or modifying tracker data.

## Tools

### `check_deadlines`

Reads active personal deadlines from Google Sheets.

Supports optional filters for:

* Company
* Role
* Stage

### `research_company`

Uses Tavily to retrieve recent web reports about company interview processes.

These are external web sources and are **not** treated as personal placement-tracker data.

### `draft_email`

Uses Ollama to create editable:

* Follow-up emails
* Thank-you emails
* Application emails

The tool only creates a draft. **It never sends email.**

### `log_application`

Creates or updates an application/opportunity and can optionally create or update its linked deadline.

Application identity is based on:

```text
company + role
```

Therefore, logging the same company and role again updates the existing application instead of creating a duplicate.

## Google Sheets Tracker

Create one Google Spreadsheet and share it with the Google service-account email as an **Editor**.

The application automatically creates the required tabs and header rows if they do not already exist.

### Applications

```text
application_id
company
role
applied
applied_date
status
notes
updated_at
```

### Deadlines

```text
deadline_id
application_id
company
role
stage
deadline_date
deadline_time
status
source
notes
```

Google Sheets is the only active persistent storage layer. There is no SQLite database used for placement tracking.

## Date Handling

The agent resolves relative dates such as:

```text
today
tomorrow
next Monday
```

against the actual system date.

An announcement is stored as `Not Applied` only when enough structured information is available.

The system never assumes that a student applied simply because an opportunity was mentioned.

## Setup

### 1. Create a virtual environment

Python 3.11+ is recommended.

```bash
py -3.11 -m venv .venv
```

Activate it on Windows:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install dependencies:

```bash
pip install -r requirements.txt
```

### 2. Install Ollama

Install Ollama and pull the configured models:

```bash
ollama pull llama3.2:3b
ollama pull llama3.2-vision:11b
```

You may alternatively use:

```text
OLLAMA_MODEL=gpt-oss:20b
```

after pulling that model.

The vision model is only required when processing image attachments. PDFs are processed locally.

### 3. Configure Google Sheets

In Google Cloud:

1. Enable the **Google Sheets API**.
2. Create a service account.
3. Download its JSON credentials.
4. Save the credentials as:

```text
credentials/service_account.json
```

5. Create a Google Spreadsheet.
6. Share the spreadsheet with the service-account email as an **Editor**.

Never commit the service-account JSON file.

### 4. Configure environment variables

Copy:

```text
.env.example
```

to:

```text
.env
```

Then configure:

```env
LLM_PROVIDER=ollama
OLLAMA_MODEL=llama3.2:3b
OLLAMA_VISION_MODEL=llama3.2-vision:11b

TAVILY_API_KEY=your_tavily_api_key
TAVILY_MAX_RESULTS=5

GOOGLE_SHEET_ID=your_google_sheet_id
GOOGLE_CREDENTIALS_FILE=credentials/service_account.json

PLACEMENT_API_URL=http://127.0.0.1:8000
```

Tavily is optional unless company research is used.

Ollama runs locally and does not require an API key.

**Do not commit `.env`, API keys, or Google service-account credentials.**

### 5. Run the application

Start the backend:

```bash
uvicorn backend.main:app --reload
```

In a separate terminal, start Streamlit:

```bash
streamlit run frontend/app.py
```

Open:

```text
http://127.0.0.1:8501
```

## API Endpoints

The FastAPI backend exposes:

| Endpoint            | Purpose                               |
| ------------------- | ------------------------------------- |
| `GET /health`       | Check backend health                  |
| `GET /applications` | Retrieve tracked applications         |
| `GET /deadlines`    | Retrieve tracked deadlines            |
| `POST /chat`        | Send a message to the placement agent |

FastAPI also provides its standard interactive API documentation when the backend is running.

## Example Conversations

### Deadline tracking

> "Any deadlines coming up this week?"

The agent reads the Google Sheets deadline tracker.

### Company research

> "What is TCS's interview process like?"

The agent uses Tavily to retrieve current web reports and returns them as sourced, non-guaranteed information.

### Email drafting

> "Draft a follow-up email to the Infosys recruiter. It has been two weeks."

The agent creates an editable draft with address placeholders.

It does not send the email.

### Application tracking

> "I just applied to Wipro for Project Engineer today."

The agent creates or updates the application using the actual current date.

### Application + deadline

> "I applied to Wipro for Project Engineer today. The assessment deadline is October 3."

The agent updates the application and creates or updates the linked assessment deadline.

### Resume / Job Description

A user can upload a resume or job-description PDF/image and ask for:

* Role-fit analysis
* Resume improvement suggestions
* Interview preparation
* Relevant skills or gaps

If the role is missing from an application record, the assistant asks for it rather than creating an incomplete record.

If no personal deadline exists in the tracker, the assistant reports that no tracker record exists instead of searching the web and fabricating a deadline.

## Project Structure

```text
placement-agent/
│
├── backend/
│   ├── agent.py
│   ├── main.py
│   └── sheets.py
│
├── frontend/
│   └── app.py
│
├── tests/
│
├── credentials/
│   └── service_account.json   # ignored by Git
│
├── .env.example
├── .gitignore
├── requirements.txt
└── README.md
```

## Tests

Run the offline test suite:

```bash
python -m unittest discover -s tests -v
```

The tests use a fake Sheets client and do not modify the real Google Spreadsheet.

The test suite covers:

* Application creation
* Application updates
* Duplicate prevention
* Linked deadlines
* Deadline filtering
* Invalid dates
* Relative dates
* Announcement records that are not applications

## Security

The project follows a local-first approach for LLM inference and separates personal tracker storage from external company research.

* `.env` is ignored by Git.
* `credentials/` is ignored by Git.
* Google service-account credentials must never be committed.
* API keys must never be committed.
* The frontend communicates with the backend rather than directly accessing credentials.
* Google Sheets is the only persistent placement-tracker storage.
* There is no Gmail API integration.
* The application does not send emails automatically.
* Tavily is used for company research, not for personal placement records.

## Limitations

* Company interview-process information from the web may be incomplete, outdated, or anecdotal.
* Tavily research should not be treated as an official company hiring policy.
* The application tracker depends on access to the configured Google Spreadsheet.
* Ollama models must be installed locally.
* Email generation produces drafts only; users are responsible for reviewing and sending them.

## License

Add your preferred open-source license here, for example MIT, if you intend to distribute the project under that license.
