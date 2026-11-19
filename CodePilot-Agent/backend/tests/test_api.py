"""
API endpoint tests.
"""
import pytest


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert "status" in data
    assert data["status"] == "ok"
    assert "version" in data


def test_health_llm_no_key(client, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    r = client.get("/api/health/llm")
    assert r.status_code == 200
    assert r.json()["status"] == "not_configured"


def test_create_conversation(client):
    r = client.post("/api/conversations", json={"title": "Test Conv", "workspace_path": "."})
    assert r.status_code == 201
    data = r.json()
    assert data["title"] == "Test Conv"
    assert "id" in data
    return data["id"]


def test_list_conversations(client):
    r = client.get("/api/conversations")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_get_conversation(client):
    # Create first
    r = client.post("/api/conversations", json={"title": "Get Test"})
    cid = r.json()["id"]
    r2 = client.get(f"/api/conversations/{cid}")
    assert r2.status_code == 200
    data = r2.json()
    assert data["id"] == cid
    assert "messages" in data


def test_update_conversation(client):
    r = client.post("/api/conversations", json={"title": "Old Title"})
    cid = r.json()["id"]
    r2 = client.patch(f"/api/conversations/{cid}", json={"title": "New Title"})
    assert r2.status_code == 200
    assert r2.json()["title"] == "New Title"


def test_delete_conversation(client):
    r = client.post("/api/conversations", json={"title": "To Delete"})
    cid = r.json()["id"]
    r2 = client.delete(f"/api/conversations/{cid}")
    assert r2.status_code == 204
    r3 = client.get(f"/api/conversations/{cid}")
    assert r3.status_code == 404


def test_add_message(client):
    r = client.post("/api/conversations", json={"title": "Msg Test"})
    cid = r.json()["id"]
    r2 = client.post(f"/api/conversations/{cid}/messages", json={
        "role": "user", "content": "Hello agent"
    })
    assert r2.status_code == 201
    assert r2.json()["content"] == "Hello agent"


def test_get_workspace(client):
    r = client.get("/api/workspace")
    assert r.status_code == 200
    assert "path" in r.json()


def test_set_workspace_invalid(client):
    r = client.post("/api/workspace", json={"path": "C:/nonexistent/path/xyz123"})
    assert r.status_code == 400


def test_settings_get(client):
    r = client.get("/api/settings")
    assert r.status_code == 200
    data = r.json()
    assert "model" in data
    assert "max_iterations" in data


def test_settings_save(client):
    r = client.post("/api/settings", json={"key": "model", "value": "gpt-4o"})
    assert r.status_code == 200
    assert r.json()["success"] is True


def test_settings_no_api_key_storage(client):
    r = client.post("/api/settings", json={"key": "api_key", "value": "sk-secret"})
    assert r.status_code == 200
    assert "error" in r.json()


def test_create_task_no_api_key(client, monkeypatch):
    from app.config import settings
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    r = client.post("/api/agent/tasks", json={"prompt": "Hello"})
    assert r.status_code == 400


def test_pending_approvals(client):
    r = client.get("/api/approvals/pending")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
