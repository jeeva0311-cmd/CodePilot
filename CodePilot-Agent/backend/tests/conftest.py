"""
Shared pytest fixtures for CodePilot Agent tests.
"""
import os
import sys
import tempfile
import pytest
from pathlib import Path
from fastapi.testclient import TestClient

# Ensure the backend package is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Point the database at a temp file for tests
os.environ.setdefault("OPENAI_API_KEY", "sk-test-key-not-real")
os.environ["DATABASE_PATH"] = str(Path(tempfile.gettempdir()) / "codepilot_test.db")


@pytest.fixture(scope="session")
def tmp_workspace(tmp_path_factory):
    """A real temporary directory used as workspace in tool tests."""
    ws = tmp_path_factory.mktemp("workspace")
    # Seed some files
    (ws / "hello.py").write_text('def hello():\n    return "Hello, World!"\n')
    (ws / "README.md").write_text("# Test Project\nThis is a test.\n")
    sub = ws / "sub"
    sub.mkdir()
    (sub / "util.py").write_text("def add(a, b):\n    return a + b\n")
    return ws


@pytest.fixture(scope="session")
def client():
    """FastAPI test client with a fresh in-memory database."""
    from app.database.database import init_db
    init_db()
    from app.main import app
    return TestClient(app)
