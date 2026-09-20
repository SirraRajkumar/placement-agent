"""Streamlit interface for the Placement Assistant Agent."""

from __future__ import annotations

import os
from typing import Any

import pandas as pd
import requests
import streamlit as st

API_URL = os.getenv("PLACEMENT_API_URL", "http://127.0.0.1:8000").rstrip("/")

st.set_page_config(page_title="Placement Assistant", page_icon="🎓", layout="centered")


def api_get(path: str) -> Any:
    response = requests.get(f"{API_URL}{path}", timeout=10)
    response.raise_for_status()
    return response.json()


def api_post(path: str, payload: dict[str, Any]) -> Any:
    response = requests.post(f"{API_URL}{path}", json=payload, timeout=90)
    response.raise_for_status()
    return response.json()


def analyse_files(files: list[Any]) -> list[dict[str, str]]:
    """Send selected files to the API only when the user sends a message."""
    response = requests.post(
        f"{API_URL}/attachments",
        files=[("files", (file.name, file.getvalue(), file.type)) for file in files],
        timeout=120,
    )
    response.raise_for_status()
    return response.json()


if "messages" not in st.session_state:
    st.session_state.messages = []

st.title("Placement Assistant")
st.caption("Your placement-season assistant")

with st.sidebar:
    try:
        api_get("/health")
        backend_connected = True
    except requests.RequestException:
        backend_connected = False
        st.error("Backend unavailable. Start FastAPI on port 8000.")
    if backend_connected:
        try:
            application_rows = api_get("/applications")
            deadline_rows = api_get("/deadlines")
        except requests.RequestException:
            application_rows, deadline_rows = [], []

        # Keep the first screen focused on conversation. The tracker appears
        # only after the student has logged at least one real application.
        if application_rows:
            st.subheader("Applications")
            frame = pd.DataFrame(application_rows)
            for _, record in frame.iterrows():
                st.markdown(f"**{record['company']}**  \\n{record['role']} · {record['status']}")
                linked = [
                    item for item in deadline_rows
                    if item.get("application_id") == record.get("application_id")
                    and item.get("status") not in {"Completed", "Missed", "Cancelled"}
                ]
                if linked:
                    next_deadline = min(linked, key=lambda item: item.get("deadline_date", ""))
                    st.caption(f"Next deadline: {next_deadline.get('deadline_date')} · {next_deadline.get('stage')}")
                st.divider()
    if st.button("Clear chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

if not st.session_state.messages:
    st.markdown("### How can I help with your placement preparation?")
    st.caption("Try checking a deadline, researching an interview process, drafting an email, or logging an application.")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])
        if message.get("tool_trace"):
            with st.expander("Agent actions", expanded=False):
                for action in message["tool_trace"]:
                    marker = "✓" if action["ok"] else "×"
                    st.write(f"{marker} `{action['tool']}`")
                    if not action["ok"]:
                        st.caption(action["error"])

prompt = st.chat_input("Message Placement Assistant...")
uploaded_files = st.file_uploader(
    "Attach a resume or job description (PDF, PNG, JPG, or WebP)",
    type=["pdf", "png", "jpg", "jpeg", "webp"],
    accept_multiple_files=True,
)
if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            try:
                attachment_data = analyse_files(uploaded_files) if uploaded_files else []
                payload = {
                    "message": prompt,
                    "history": [
                        {"role": message["role"], "content": message["content"]}
                        for message in st.session_state.messages[:-1]
                    ],
                    "attachments": attachment_data,
                }
                result = api_post("/chat", payload)
                st.markdown(result["reply"])
                if result["tool_trace"]:
                    with st.expander("Agent actions", expanded=False):
                        for action in result["tool_trace"]:
                            marker = "✓" if action["ok"] else "×"
                            st.write(f"{marker} `{action['tool']}`")
                st.session_state.messages.append(
                    {"role": "assistant", "content": result["reply"], "tool_trace": result["tool_trace"]}
                )
                st.rerun()
            except requests.HTTPError as exc:
                detail = exc.response.json().get("detail", exc.response.text)
                st.error(f"The agent could not respond: {detail}")
            except requests.RequestException as exc:
                st.error(f"Could not reach the backend: {exc}")
