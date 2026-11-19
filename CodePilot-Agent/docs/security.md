# CodePilot Agent — Security Documentation

## Workspace Sandbox

The agent can only access files inside the **selected workspace directory**.

Every file path provided by the LLM is processed by `validate_path()` before any file operation:

```python
def validate_path(path, workspace_root):
    workspace = Path(workspace_root).resolve()
    target = (workspace / path).resolve()
    target.relative_to(workspace)   # raises ValueError if outside
    return target
```

This blocks:
- `../../etc/passwd` — path traversal
- `C:\Windows\System32\cmd.exe` — absolute paths outside workspace
- Symlinks that point outside the workspace (resolved before check)

## Command Allowlist

Only development-related commands are allowed. The check runs before any subprocess is spawned.

**Allowed prefixes:** `python`, `pytest`, `pip`, `node`, `npm`, `npx`, `git status/log/diff/branch/show`, `echo`, `dir`, `ls`, `java`, `mvn`, `gradle`, `dotnet`, `ruby`, `cargo`, `go`, `make`

**Blocked patterns (regex):**
- `rm\s+-rf` — recursive deletion
- `rmdir\s+/s` — Windows recursive deletion
- `format\s+[a-z]:` — disk format
- `shutdown` / `reboot` — system shutdown
- `reg\s+(add|delete)` — registry modification
- `net\s+(user|localgroup)` — user account changes
- `curl|wget ... | sh` — remote code execution via pipe
- `powershell.*-enc` — encoded PowerShell commands
- `Remove-Item.*-Recurse.*-Force` — PowerShell rm -rf equivalent
- `icacls` / `cacls` — permission changes

## Tool Risk Levels

| Risk | Tools | Default approval |
|------|-------|-----------------|
| Low | `list_files`, `read_file`, `search_files`, `get_project_info`, `git_status` | Never required |
| Medium | `write_file`, `edit_file`, `run_command`, `run_tests` | Optional (off by default) |
| High | `delete_file`, `run_destructive_command` | Always required (on by default) |

## Approval Workflow

1. Agent loop calls `_request_approval()` before executing a high/medium-risk tool.
2. An `ApprovalRequest` record is saved to SQLite with `status = "pending"`.
3. The agent loop registers with `ApprovalService` and **blocks** on a `threading.Event`.
4. An SSE event is sent to the browser: `approval_requested`.
5. The browser renders an approval card in the chat with Approve / Reject buttons.
6. The user clicks a button → `POST /api/approvals/{id}/decide`.
7. `ApprovalService.signal()` sets the event, unblocking the agent loop thread.
8. If the user approves, the tool executes normally.
9. If the user rejects or the 5-minute timeout fires, the agent records a rejection and continues with the next step.

The agent **never** silently executes a high-risk operation.

## Secret Protection

- API keys are read from `.env` only, never from the database.
- The `POST /api/settings` endpoint rejects any key name containing "api_key" or "secret".
- The `.gitignore` excludes `.env` from version control.
- `contains_secret()` and `redact_secrets()` helpers detect and mask common secret patterns in output.

## What Is NOT Sandboxed

- The agent runs with the same OS permissions as the user who starts it.
- There is no Docker/container isolation.
- Commands run via `subprocess.run(shell=True)`, protected only by the allowlist.
- For production use, running inside a container or VM is recommended.
