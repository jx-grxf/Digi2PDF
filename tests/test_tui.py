from __future__ import annotations

from types import SimpleNamespace

from digi2pdf import tui


def test_ask_password_uses_masked_questionary_prompt(monkeypatch) -> None:
    calls: list[dict[str, object]] = []

    def fake_password(message: str, **kwargs: object) -> SimpleNamespace:
        calls.append({"message": message, **kwargs})
        return SimpleNamespace(ask=lambda: "secret")

    monkeypatch.setattr(tui.questionary, "password", fake_password)

    assert tui.ask_password() == "secret"
    assert calls[0]["message"] == "Digi4School password"
    assert calls[0]["qmark"] == "*"


def test_ask_books_separates_all_from_manual_selection(monkeypatch) -> None:
    monkeypatch.setattr(tui, "ask_book_scope", lambda: "all")

    assert tui.ask_books(["Math", "English"]) == "all"


def test_ask_books_manual_selection_has_no_all_choice(monkeypatch) -> None:
    captured_choices: list[object] = []
    monkeypatch.setattr(tui, "ask_book_scope", lambda: "select")

    def fake_checkbox(_message: str, *, choices: list[object], **_kwargs: object) -> SimpleNamespace:
        captured_choices.extend(choices)
        return SimpleNamespace(ask=lambda: [1])

    monkeypatch.setattr(tui.questionary, "checkbox", fake_checkbox)

    selected = tui.ask_books(["Math", "English"])

    assert selected == [tui.BookChoice(title="English", index=1)]
    assert [choice.value for choice in captured_choices] == [0, 1]
