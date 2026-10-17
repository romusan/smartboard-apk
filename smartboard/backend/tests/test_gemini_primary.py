import pytest

from smartboard_backend import tutor_adapter
from smartboard_backend.models import AiRequest, AiResponse


@pytest.fixture
def question():
    return AiRequest(action="explain", session_id="provider-test", page_id="page-1",
                     recognized_text="Explica la deformación elástica")


def test_gemini_answers_without_starting_local_tutor(monkeypatch, question):
    expected = AiResponse(kind="text", content="Respuesta de Gemini", metadata={"provider": "Gemini"})
    monkeypatch.setattr(tutor_adapter, "answer_with_gemini", lambda request, prompt: expected)
    def unexpected(request):
        pytest.fail("The local tutor must not run when Gemini succeeds")
    monkeypatch.setattr(tutor_adapter, "_ask_tutor_fallback_sync", unexpected)
    assert tutor_adapter._ask_tutor_sync(question) is expected


def test_local_tutor_runs_only_after_gemini_failure(monkeypatch, question):
    calls = []
    def unavailable(request, prompt):
        calls.append("gemini")
        raise TimeoutError("unavailable")
    def fallback(request):
        calls.append("local")
        return AiResponse(kind="text", content="Respaldo local")
    monkeypatch.setattr(tutor_adapter, "answer_with_gemini", unavailable)
    monkeypatch.setattr(tutor_adapter, "_ask_tutor_fallback_sync", fallback)
    result = tutor_adapter._ask_tutor_sync(question)
    assert calls == ["gemini", "local"]
    assert result.metadata["primary_provider"] == "gemini"
    assert result.metadata["fallback_used"] is True


def test_explicit_diagram_keeps_local_renderer(monkeypatch, question):
    question.action = "outline"
    expected = AiResponse(kind="image", content="Esquema")
    monkeypatch.setattr(tutor_adapter, "_ask_tutor_fallback_sync", lambda request: expected)
    assert tutor_adapter._ask_tutor_sync(question) is expected
