"""FastAPI service for the Placement Assistant Agent."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from backend.agent import AgentConfigurationError, run_agent
from backend.attachments import AttachmentError, analyse_attachment, attachment_context
from backend.sheets import SheetsError, get_storage


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield


app = FastAPI(title="Placement Assistant Agent API", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://127.0.0.1:8501"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=12_000)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=12_000)
    history: list[ChatTurn] = Field(default_factory=list, max_length=30)
    attachments: list[dict[str, str]] = Field(default_factory=list, max_length=3)


class ChatResponse(BaseModel):
    reply: str
    tool_trace: list[dict]


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/applications")
def applications() -> list[dict]:
    try:
        return get_storage().get_applications()
    except SheetsError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/deadlines")
def deadlines() -> list[dict]:
    try:
        return get_storage().get_deadlines()
    except SheetsError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.post("/attachments")
async def attachments(files: list[UploadFile] = File(...)) -> list[dict[str, str]]:
    """Extract temporary chat context from uploaded PDFs and images."""
    if len(files) > 3:
        raise HTTPException(status_code=422, detail="Attach at most three files at a time.")
    analysed: list[dict[str, str]] = []
    for file in files:
        try:
            analysed.append(analyse_attachment(file.filename or "attachment", file.content_type or "", await file.read()))
        except AttachmentError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    return analysed


@app.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    try:
        context = attachment_context(request.attachments)
        message = request.message if not context else f"{request.message}\n\nReference attachments:\n{context}"
        result = run_agent(message, [turn.model_dump() for turn in request.history])
    except AgentConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ChatResponse(reply=result.reply, tool_trace=result.tool_trace)
