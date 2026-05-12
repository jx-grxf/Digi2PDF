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


def test_ask_books_manual_selection_uses_prefix_search_without_jk_keys(monkeypatch) -> None:
    captured_choices: list[object] = []
    captured_kwargs: dict[str, object] = {}
    monkeypatch.setattr(tui, "ask_book_scope", lambda: "select")

    def fake_checkbox(_message: str, *, choices: list[object], **_kwargs: object) -> SimpleNamespace:
        captured_choices.extend(choices)
        captured_kwargs.update(_kwargs)
        return SimpleNamespace(ask=lambda: [1])

    monkeypatch.setattr(tui.questionary, "checkbox", fake_checkbox)

    selected = tui.ask_books(["Math", "English"])

    assert selected == [tui.BookChoice(title="English", index=1)]
    assert [choice.value for choice in captured_choices] == [0, 1]
    assert captured_kwargs["use_search_filter"] is True
    assert captured_kwargs["use_jk_keys"] is False


def test_ask_books_retries_empty_manual_selection(monkeypatch) -> None:
    calls = 0
    monkeypatch.setattr(tui, "ask_book_scope", lambda: "select")
    monkeypatch.setattr(tui, "ask_confirm", lambda _message, default=True: True)

    def fake_checkbox(_message: str, *, choices: list[object], **_kwargs: object) -> SimpleNamespace:
        nonlocal calls
        calls += 1
        return SimpleNamespace(ask=lambda: [] if calls == 1 else [0])

    monkeypatch.setattr(tui.questionary, "checkbox", fake_checkbox)

    assert tui.ask_books(["Math"]) == [tui.BookChoice(title="Math", index=0)]
    assert calls == 2


def test_ask_books_can_cancel_after_empty_manual_selection(monkeypatch) -> None:
    monkeypatch.setattr(tui, "ask_book_scope", lambda: "select")
    monkeypatch.setattr(tui, "ask_confirm", lambda _message, default=True: False)
    monkeypatch.setattr(
        tui.questionary,
        "checkbox",
        lambda *_args, **_kwargs: SimpleNamespace(ask=lambda: []),
    )

    assert tui.ask_books(["Math"]) is None
