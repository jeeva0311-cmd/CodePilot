"""
Security / sandbox tests.
"""
import pytest
from pathlib import Path


def test_path_inside_workspace(tmp_path):
    from app.security.sandbox import validate_path
    result = validate_path("sub/file.py", str(tmp_path))
    assert str(result).startswith(str(tmp_path))


def test_path_traversal_blocked(tmp_path):
    from app.security.sandbox import validate_path
    with pytest.raises(ValueError, match="outside the workspace"):
        validate_path("../../etc/passwd", str(tmp_path))


def test_absolute_path_outside_blocked(tmp_path):
    from app.security.sandbox import validate_path
    with pytest.raises(ValueError):
        validate_path("C:/Windows/System32/cmd.exe", str(tmp_path))


def test_is_safe_path_true(tmp_path):
    from app.security.sandbox import is_safe_path
    assert is_safe_path("hello.py", str(tmp_path)) is True


def test_is_safe_path_false(tmp_path):
    from app.security.sandbox import is_safe_path
    assert is_safe_path("../../secret", str(tmp_path)) is False


def test_command_allowed_python():
    from app.security.sandbox import validate_command
    ok, reason = validate_command("python main.py")
    assert ok is True


def test_command_allowed_pytest():
    from app.security.sandbox import validate_command
    ok, _ = validate_command("pytest tests/")
    assert ok is True


def test_command_blocked_rm():
    from app.security.sandbox import validate_command
    ok, reason = validate_command("rm -rf /")
    assert ok is False


def test_command_blocked_format():
    from app.security.sandbox import validate_command
    ok, reason = validate_command("format C:")
    assert ok is False


def test_command_blocked_shutdown():
    from app.security.sandbox import validate_command
    ok, _ = validate_command("shutdown -s -t 0")
    assert ok is False


def test_command_unknown_blocked():
    from app.security.sandbox import validate_command
    ok, _ = validate_command("some_random_tool --hack")
    assert ok is False


def test_secret_detection():
    from app.security.sandbox import contains_secret
    assert contains_secret("api_key = sk-abc123defghi456jklmno") is True
    assert contains_secret("x = 42") is False


def test_secret_redaction():
    from app.security.sandbox import redact_secrets
    text = "my key: sk-abcdefghij1234567890xyz"
    out = redact_secrets(text)
    assert "sk-" not in out
    assert "[REDACTED]" in out


def test_risk_classification():
    from app.security.sandbox import get_tool_risk
    assert get_tool_risk("list_files") == "low"
    assert get_tool_risk("read_file") == "low"
    assert get_tool_risk("write_file") == "medium"
    assert get_tool_risk("delete_file") == "high"


def test_write_outside_workspace_blocked(tmp_path):
    from app.tools.filesystem import write_file
    result = write_file(str(tmp_path), "../../evil.py", "malicious code")
    assert result["success"] is False
    assert "error" in result
