# CodePilot Agent

> A locally-running AI coding assistant that actually executes code — not a chatbot that pretends to.

## Project Overview

CodePilot Agent is a full-stack AI software development assistant. You describe a coding task in plain English, and the agent plans, writes code, runs commands, fixes errors, runs tests, and reports back — all autonomously with human approval for risky operations.

It demonstrates the core architecture of tools like Claude Code, Cursor Agent, and GitHub Copilot Agent, implemented from scratch as a standalone application.

---

## Features

| Category | Features |
|---|---|
| **AI Agent** | Real OpenAI LLM integration, iterative tool-call loop (up to 12 iterations), task planning, context management, autonomous debugging |
| **Tools** | List/read/write/edit files, search codebase, run commands, run tests, git status, project inspection |
| **Safety** | Workspace sandbox (path traversal prevention), command allowlist/blocklist, risk classification (low/medium/high), human approval workflow |
| **UI** | Dark developer theme, chat interface, real-time activity panel, file explorer, task plan display, tool execution cards, file change tracker |
| **Persistence** | SQLite database — conversations, messages, tasks, tool executions, file changes, settings |
| **Real-time** | Server-Sent Events (SSE) for live agent updates |

---

## Technology Stack

**Backend:** Python 3.11+ · FastAPI · Uvicorn · SQLAlchemy · SQLite · OpenAI Python SDK  
**Frontend:** HTML · CSS · Vanilla JavaScript · Fetch API · SSE  
**Testing:** pytest

---

## Architecture

```
CodePilot-Agent/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app, startup, routers
│   │   ├── config/settings.py   # All configuration from .env
│   │   ├── agent/
│   │   │   ├── agent.py         # CodePilotAgent — tool dispatcher
│   │   │   ├── loop.py          # AgentLoop — iterative execution engine
│   │   │   ├── llm_client.py    # OpenAI SDK wrapper
│   │   │   ├── prompts.py       # System and planning prompts
│   │   │   ├── context.py       # LLM message history manager
│   │   │   └── planner.py       # Task planner (LLM-generated steps)
│   │   ├── tools/
│   │   │   ├── registry.py      # OpenAI function-call schemas
│   │   │   ├── filesystem.py    # list_files, read_file, write_file, edit_file
│   │   │   ├── search.py        # search_files
│   │   │   ├── terminal.py      # run_command
│   │   │   ├── testing.py       # run_tests (auto-detect pytest/jest)
│   │   │   └── git.py           # git_status
│   │   ├── security/sandbox.py  # Path validation, command allowlist, risk levels
│   │   ├── workspace/manager.py # Workspace selection and file tree
│   │   ├── database/database.py # SQLAlchemy engine, session, init
│   │   ├── models/              # ORM models (Conversation, Message, AgentTask…)
│   │   ├── services/
│   │   │   ├── event_bus.py     # SSE event publisher/subscriber
│   │   │   └── approval_service.py  # Blocking approval wait/signal
│   │   └── api/                 # FastAPI routers
│   │       ├── health.py
│   │       ├── conversations.py
│   │       ├── agent.py         # Task creation, SSE stream, cancel
│   │       ├── workspace.py
│   │       ├── files.py
│   │       ├── settings.py
│   │       └── approvals.py
│   └── tests/                   # 57 pytest tests
├── frontend/
│   ├── index.html               # Single-page application
│   ├── styles/main.css          # Dark developer theme
│   └── scripts/
│       ├── api.js               # Backend fetch wrapper
│       ├── markdown.js          # Lightweight markdown renderer
│       └── app.js               # Full UI application logic
├── .env.example                 # Environment template
├── .gitignore
├── requirements.txt
├── run.bat                      # One-click Windows launcher
└── run_tests.bat
```

---

## Agent Execution Loop

```
User submits task
       │
       ▼
  Generate task plan (LLM)
       │
       ▼
  ┌──────────────────────────────┐
  │  Iteration (max 12)          │
  │                              │
  │  LLM step()                  │
  │       │                      │
  │       ├── text response  ────┼──► Append to chat, check if done
  │       │                      │
  │       └── tool_calls         │
  │              │               │
  │              ▼               │
  │       Risk check             │
  │              │               │
  │   high risk? ├── YES ──► Approval gate (block until user decides)
  │              │               │
  │              ▼               │
  │       Execute tool           │
  │       (filesystem/terminal   │
  │        /search/git/tests)    │
  │              │               │
  │              ▼               │
  │       Feed result to LLM     │
  │       (tool_result message)  │
  └──────────────────────────────┘
       │
       ▼
  Final summary → chat
  File changes → DB
  Task status = completed
```

---

## Tools

| Tool | Risk | Description |
|---|---|---|
| `list_files` | Low | Recursive directory listing with depth limit |
| `read_file` | Low | Read file content (max 512 KB) |
| `write_file` | Medium | Create or overwrite a file |
| `edit_file` | Medium | Replace exact string in existing file |
| `search_files` | Low | Regex/text search across workspace |
| `get_project_info` | Low | Detect language, framework, structure |
| `run_command` | Medium | Execute allowed development commands |
| `run_tests` | Medium | Auto-detect and run pytest/jest |
| `git_status` | Low | Branch, modified/untracked files |

---

## Security

- **Workspace sandbox** — all file paths are resolved and validated to stay inside the selected workspace directory. Path traversal (`../../`) is blocked.
- **Command allowlist** — only development commands (python, pytest, npm, git status, etc.) are permitted. Destructive commands (rm -rf, format, shutdown, etc.) are blocked by pattern matching.
- **Risk classification** — each tool is classified low/medium/high risk.
- **Approval workflow** — high-risk operations block the agent loop and display an approval card in the UI. The agent waits up to 5 minutes for the user's decision.
- **Secret protection** — API keys are never stored in the database. The settings endpoint rejects attempts to store values with "api_key" or "secret" in the key name.

---

## Database Schema

| Table | Purpose |
|---|---|
| `conversations` | Chat conversation metadata |
| `messages` | Individual chat messages (user/assistant/tool) |
| `agent_tasks` | Task records with status, iterations, final response |
| `task_steps` | Plan steps for each task |
| `tool_executions` | Every tool call with inputs, outputs, duration |
| `file_changes` | Files created/modified/deleted per task |
| `approval_requests` | Approval records with decision and timestamp |
| `settings` | Key/value configuration store |

---

## Installation

### Requirements
- Python 3.11 or newer
- An OpenAI API key (get one at https://platform.openai.com)

### Steps

```bash
# 1. Clone or download the project
cd CodePilot-Agent

# 2. Copy the environment template
copy .env.example .env

# 3. Open .env and add your API key
# OPENAI_API_KEY=sk-your-key-here

# 4. Install dependencies
pip install -r requirements.txt

# 5. Start the backend
cd backend
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Or simply double-click **`run.bat`** on Windows — it handles everything automatically.

---

## Running the Application

```
run.bat
```

Then open: **http://127.0.0.1:8000**

The UI will load with a "API Key not configured" warning if you haven't added your key yet — the app still starts and shows the interface.

---

## Running Tests

```
run_tests.bat
```

Or manually:
```bash
cd backend
python -m pytest tests/ -v --tb=short
```

**Result: 57 tests, 57 passed.**

---

## Example Tasks

Try these in the chat interface:

1. **Project inspection:**  
   `Inspect this project and explain its structure, main files, and how it runs.`

2. **Code creation:**  
   `Create a Python calculator with add, subtract, multiply, divide, input validation, and unit tests.`

3. **Code search:**  
   `Search the codebase for any TODO comments and summarize them.`

4. **Git status:**  
   `Check git status and show what files have changed.`

5. **Approval workflow:**  
   `Delete the file test_sample.py` — this will trigger an approval request.

---

## Configuration (.env)

| Variable | Default | Description |
|---|---|---|
| `OPENAI_API_KEY` | — | **Required.** Your OpenAI API key |
| `OPENAI_MODEL` | `gpt-4o-mini` | Model to use |
| `MAX_AGENT_ITERATIONS` | `12` | Max tool-call loops per task |
| `COMMAND_TIMEOUT` | `30` | Shell command timeout (seconds) |
| `REQUIRE_APPROVAL_FOR_HIGH_RISK` | `true` | Block until user approves high-risk ops |
| `PORT` | `8000` | Server port |

---

## Limitations

- The OpenAI API key must be added to `.env` manually before the agent can run tasks (the UI starts without it).
- The command allowlist covers common dev tools; niche commands need to be added to `security/sandbox.py`.
- Very long tasks may hit the 12-iteration limit; increase `MAX_AGENT_ITERATIONS` for complex work.
- The agent runs commands in-process (via subprocess), not in a Docker container — it relies on the workspace sandbox and command allowlist for safety.
- File picker is a text input (no native OS folder browser) for cross-platform simplicity.
