"""
Tool unit tests — use a real temp workspace, no mocking.
"""
import pytest
from pathlib import Path


def test_list_files(tmp_workspace):
    from app.tools.filesystem import list_files
    result = list_files(str(tmp_workspace))
    assert "tree" in result
    assert result["total_shown"] > 0
    names = [item["name"] for item in result["tree"]]
    assert "hello.py" in names


def test_read_file(tmp_workspace):
    from app.tools.filesystem import read_file
    result = read_file(str(tmp_workspace), "hello.py")
    assert "content" in result
    assert "Hello" in result["content"]
    assert result["lines"] == 2


def test_read_file_not_found(tmp_workspace):
    from app.tools.filesystem import read_file
    result = read_file(str(tmp_workspace), "nonexistent.py")
    assert "error" in result


def test_write_file(tmp_workspace):
    from app.tools.filesystem import write_file, read_file
    result = write_file(str(tmp_workspace), "new_file.py", "x = 42\n")
    assert result["success"] is True
    assert result["action"] == "created"
    # Verify content
    r2 = read_file(str(tmp_workspace), "new_file.py")
    assert "x = 42" in r2["content"]


def test_write_file_creates_dirs(tmp_workspace):
    from app.tools.filesystem import write_file
    result = write_file(str(tmp_workspace), "deep/nested/file.py", "pass\n")
    assert result["success"] is True
    assert (tmp_workspace / "deep" / "nested" / "file.py").exists()


def test_edit_file(tmp_workspace):
    from app.tools.filesystem import write_file, edit_file, read_file
    write_file(str(tmp_workspace), "edit_me.py", "x = 1\ny = 2\n")
    result = edit_file(str(tmp_workspace), "edit_me.py", "x = 1", "x = 99")
    assert result["success"] is True
    r2 = read_file(str(tmp_workspace), "edit_me.py")
    assert "x = 99" in r2["content"]


def test_edit_file_string_not_found(tmp_workspace):
    from app.tools.filesystem import write_file, edit_file
    write_file(str(tmp_workspace), "edit2.py", "x = 1\n")
    result = edit_file(str(tmp_workspace), "edit2.py", "DOES_NOT_EXIST", "new")
    assert result["success"] is False
    assert "error" in result


def test_search_files(tmp_workspace):
    from app.tools.search import search_files
    result = search_files(str(tmp_workspace), "def hello")
    assert result["total_matches"] >= 1
    assert result["results"][0]["file"].endswith("hello.py")


def test_search_files_no_match(tmp_workspace):
    from app.tools.search import search_files
    result = search_files(str(tmp_workspace), "ZZZNOMATCH999")
    assert result["total_matches"] == 0


def test_search_files_case_insensitive(tmp_workspace):
    from app.tools.search import search_files
    result = search_files(str(tmp_workspace), "HELLO", case_sensitive=False)
    assert result["total_matches"] >= 1


def test_get_project_info(tmp_workspace):
    from app.tools.filesystem import get_project_info
    result = get_project_info(str(tmp_workspace))
    assert "languages" in result
    assert "Python" in result["languages"]
    assert "structure_summary" in result


def test_run_command_success(tmp_workspace):
    from app.tools.terminal import run_command
    result = run_command(str(tmp_workspace), "python --version")
    assert result["exit_code"] == 0
    assert "Python" in result["stdout"] or "Python" in result["stderr"]


def test_run_command_blocked(tmp_workspace):
    from app.tools.terminal import run_command
    result = run_command(str(tmp_workspace), "rm -rf /")
    assert result["success"] is False
    assert "error" in result


def test_run_command_timeout(tmp_workspace):
    from app.tools.terminal import run_command
    # Python sleep longer than timeout
    result = run_command(str(tmp_workspace), "python -c \"import time; time.sleep(60)\"", timeout=2)
    # Either times out or is blocked; in either case success should be False
    assert result["exit_code"] != 0 or result.get("timed_out") is True


def test_run_tests_no_tests(tmp_workspace):
    from app.tools.testing import run_tests
    # Workspace has no tests, pytest will exit 5 (no tests collected)
    result = run_tests(str(tmp_workspace))
    # Exit code 5 = no tests; that's acceptable
    assert "framework" in result


def test_run_tests_with_tests(tmp_path):
    from app.tools.filesystem import write_file
    from app.tools.testing import run_tests
    write_file(str(tmp_path), "test_sample.py",
               "def test_add():\n    assert 1 + 1 == 2\n")
    result = run_tests(str(tmp_path))
    assert result["summary"]["passed"] >= 1
    assert result["summary"]["failed"] == 0


def test_git_status_non_repo(tmp_workspace):
    from app.tools.git import git_status
    result = git_status(str(tmp_workspace))
    # tmp_workspace is not a git repo (unless it happens to be inside one)
    assert "is_git_repo" in result
