from __future__ import annotations

from api import model_router


def test_gemini_empty_answer_falls_back_to_ollama(monkeypatch) -> None:
    calls: list[str] = []

    def gemini(*args, **kwargs):
        calls.append("gemini")
        return ""

    def ollama(*args, **kwargs):
        calls.append("ollama")
        return "Jawaban lokal."

    monkeypatch.setitem(model_router.PROVIDERS, "gemini", gemini)
    monkeypatch.setitem(model_router.PROVIDERS, "ollama", ollama)

    answer = model_router.build_grounded_answer(
        "Pertanyaan",
        [{"content": "Bukti"}],
        language="ID",
        model="gemini",
    )

    assert answer == "Jawaban lokal."
    assert calls == ["gemini", "ollama"]


def test_evaluation_mode_does_not_switch_provider(monkeypatch) -> None:
    calls: list[str] = []

    def gemini(*args, **kwargs):
        calls.append("gemini")
        return ""

    def ollama(*args, **kwargs):
        calls.append("ollama")
        return "Tidak boleh dipakai."

    monkeypatch.setitem(model_router.PROVIDERS, "gemini", gemini)
    monkeypatch.setitem(model_router.PROVIDERS, "ollama", ollama)

    answer = model_router.build_grounded_answer(
        "Question",
        [{"content": "Evidence"}],
        language="EN",
        model="gemini",
        evaluation_mode=True,
    )

    assert answer == ""
    assert calls == ["gemini"]
