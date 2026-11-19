"""
Tool registry — central list of all available tools with their OpenAI
function-calling schemas and risk classifications.
"""
from app.security.sandbox import get_tool_risk

# ── OpenAI tool schemas ────────────────────────────────────────────────────────
TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "List files and directories in the workspace. Returns a tree structure.",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory": {"type": "string", "description": "Subdirectory to list (relative to workspace root). Empty for root."},
                    "max_depth": {"type": "integer", "description": "Maximum depth to recurse (default 3).", "default": 3},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the content of a file in the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path relative to workspace root."},
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Create a new file or completely overwrite an existing file.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path relative to workspace root."},
                    "content": {"type": "string", "description": "Full file content to write."},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "edit_file",
            "description": "Edit an existing file by replacing a specific string with a new string. The old_string must match exactly.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "File path relative to workspace root."},
                    "old_string": {"type": "string", "description": "Exact text to find and replace."},
                    "new_string": {"type": "string", "description": "Replacement text."},
                },
                "required": ["path", "old_string", "new_string"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": "Search for a pattern in files within the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Text or regex pattern to search for."},
                    "directory": {"type": "string", "description": "Directory to search in (relative). Empty for workspace root."},
                    "file_pattern": {"type": "string", "description": "Glob pattern to filter files (e.g. '*.py'). Empty for all files."},
                    "case_sensitive": {"type": "boolean", "description": "Case-sensitive search (default false).", "default": False},
                    "max_results": {"type": "integer", "description": "Maximum results to return (default 50).", "default": 50},
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_project_info",
            "description": "Analyze the workspace and return project metadata: type, language, frameworks, main files, structure.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_command",
            "description": "Run a development command (python, pytest, npm, git, etc.) in the workspace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {"type": "string", "description": "The command to execute."},
                    "working_directory": {"type": "string", "description": "Subdirectory to run in (relative to workspace). Empty for workspace root."},
                    "timeout": {"type": "integer", "description": "Timeout in seconds (default 30)."},
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_tests",
            "description": "Automatically detect the test framework and run tests for the project.",
            "parameters": {
                "type": "object",
                "properties": {
                    "test_path": {"type": "string", "description": "Specific test file or directory (optional). Empty to run all tests."},
                    "framework": {"type": "string", "description": "Test framework to use: 'pytest', 'unittest', 'jest', or 'auto' (default)."},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "git_status",
            "description": "Return the Git status of the workspace: branch, modified files, untracked files.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
]


def get_all_schemas() -> list[dict]:
    return TOOL_SCHEMAS


def get_tool_names() -> list[str]:
    return [t["function"]["name"] for t in TOOL_SCHEMAS]
