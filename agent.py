"""Small command-line entry point for the Placement Assistant Agent.

The web UI is started with ``streamlit run frontend/app.py``. This file remains
as a convenient way to try one prompt from a terminal.
"""

from backend.agent import run_agent


if __name__ == "__main__":
    prompt = input("Placement Assistant > ").strip()
    if prompt:
        print(run_agent(prompt).reply)
