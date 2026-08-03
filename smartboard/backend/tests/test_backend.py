from fastapi.testclient import TestClient
from smartboard_backend.main import app

client = TestClient(app)

def test_create_session():
    response = client.post("/sessions")
    assert response.status_code == 200
    assert "session_id" in response.json()

def test_history_empty():
    response = client.get("/sessions/test-history-empty-never-written")
    assert response.status_code == 200
    assert response.json()["messages"] == []

def test_websocket_ack():
    with client.websocket_connect("/ws/demo-test") as ws:
        first = ws.receive_json()
        assert first["type"] == "sync_state"
        ws.send_json({"type": "stroke_end", "session_id": "demo-test", "client_id": "test", "page_id": "page-1", "stroke_id": "s1", "payload": {"stroke": {"id": "s1", "page_id": "page-1", "points": []}}})
        ack = ws.receive_json()
        assert ack["type"] == "ack"


def test_closed_curve_generates_unique_mechanism_simulation():
    import math

    points = [
        {"x": 0.5 + 0.22 * math.cos(i * 2 * math.pi / 48),
         "y": 0.5 + 0.16 * math.sin(i * 2 * math.pi / 48),
         "pressure": 1.0, "t": i}
        for i in range(49)
    ]
    points[-1] = points[0] | {"t": 49}
    payload = {
        "action": "mechanism_synthesis", "subject": "mecanismos",
        "session_id": "demo-test", "page_id": "page-1",
        "strokes": [{"page_id": "page-1", "points": points}],
    }
    response = client.post("/ai/query", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "threejs"
    assert body["metadata"]["method"] == "PSO-TASS + graph families"
    assert body["metadata"]["simulation_url"].endswith(".html")


def test_atomic_interaction_opens_lennard_jones_simulation():
    payload = {
        "action": "outline",
        "subject": "materiales",
        "session_id": "demo-test",
        "page_id": "page-1",
        "recognized_text": "atomic interaction",
    }
    response = client.post("/ai/query", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["kind"] == "threejs"
    assert body["metadata"]["model"] == "lennard-jones"
    assert body["metadata"]["simulation_url"] == "/static/atomic_energy.html"
