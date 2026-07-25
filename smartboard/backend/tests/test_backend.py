from fastapi.testclient import TestClient
from smartboard_backend.main import app

client = TestClient(app)

def test_create_session():
    response = client.post("/sessions")
    assert response.status_code == 200
    assert "session_id" in response.json()

def test_history_empty():
    response = client.get("/sessions/demo-test")
    assert response.status_code == 200
    assert response.json()["messages"] == []

def test_websocket_ack():
    with client.websocket_connect("/ws/demo-test") as ws:
        first = ws.receive_json()
        assert first["type"] == "sync_state"
        ws.send_json({"type": "stroke_end", "session_id": "demo-test", "client_id": "test", "page_id": "page-1", "stroke_id": "s1", "payload": {"stroke": {"id": "s1", "page_id": "page-1", "points": []}}})
        ack = ws.receive_json()
        assert ack["type"] == "ack"
