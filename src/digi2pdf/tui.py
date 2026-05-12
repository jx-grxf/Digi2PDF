from __future__ import annotations

from pathlib import Path

import questionary
from questionary import Choice

from digi2pdf.credentials import StoredCredentials
from digi2pdf.models import BookChoice, OcrProfile
from digi2pdf.theme import THEME

OCR_PROFILES = {
    "fast": OcrProfile("fast", "Fast - lower optimization, best for large books", 1, 0.9),
    "balanced": OcrProfile("balanced", "Balanced - recommended", 2, 1.4),
    "best": OcrProfile("best", "Best - strongest optimization, slowest", 3, 2.2),
}

LOGIN_RETRY = "retry"
LOGIN_DIFFERENT = "different"
LOGIN_CLEAR = "clear"
LOGIN_CANCEL = "cancel"

RUNTIME_RETRY = "retry"
RUNTIME_CANCEL = "cancel"

OCR_RETRY = "retry"
OCR_KEEP_PDF = "keep_pdf"
OCR_FAIL = "fail"


def ask_delay(default: float = 0.5) -> float:
    answer = questionary.text(
        "Delay between pages in seconds",
        default=str(default),
        instruction="Increase this on slow connections.",
        style=_style(),
    ).ask()
    if answer is None or answer.strip() == "":
        return default
    try:
        value = float(answer)
    except ValueError:
        return default
    return max(0.1, value)


def ask_output_dir(default: Path) -> Path:
    answer = questionary.text(
        "Export location",
        default=str(default),
        instruction="Existing or new folder path.",
        style=_style(),
    ).ask()
    return Path(answer or default).expanduser().resolve()


def ask_credentials(stored: StoredCredentials | None = None) -> tuple[str, str, bool]:
    if stored and ask_confirm(f"Use saved login for {stored.email}?", default=True):
        return stored.email, stored.password, False

    email_default = stored.email if stored else ""
    email = questionary.text("Digi4School email", default=email_default, style=_style()).ask()
    password = ask_password()
    remember = ask_confirm("Save login securely in the system keychain?", default=True)
    return (email or "").strip(), password, remember


def ask_password() -> str:
    password = questionary.password(
        "Digi4School password",
        qmark="*",
        style=_style(),
    ).ask()
    return password or ""


def ask_first_run() -> bool:
    return not ask_confirm("Have you used Digi2PDF before?", default=True)


def ask_book_scope() -> str | None:
    selected = questionary.select(
        "What should Digi2PDF export?",
        choices=[
            Choice(title="All visible books", value="all"),
            Choice(title="Choose books manually", value="select"),
            Choice(title="Cancel", value="cancel"),
        ],
        use_indicator=True,
        use_shortcuts=False,
        style=_style(),
    ).ask()
    if selected in (None, "cancel"):
        return None
    return str(selected)


def ask_books(book_names: list[str]) -> list[BookChoice] | str | None:
    scope = ask_book_scope()
    if scope is None:
        return None
    if scope == "all":
        return "all"

    choices: list[Choice] = [
        Choice(title=name, value=index) for index, name in enumerate(book_names)
    ]
    while True:
        selected = questionary.checkbox(
            "Choose ebooks with Space, then press Enter",
            choices=choices,
            use_search_filter=True,
            use_jk_keys=False,
            style=_style(),
        ).ask()
        if selected is None:
            return None
        if selected:
            return [BookChoice(title=book_names[int(index)], index=int(index)) for index in selected]
        if not ask_confirm("No books selected. Choose books now?", default=True):
            return None


def ask_sub_book(book_names: list[str]) -> BookChoice | None:
    selected = questionary.select(
        "Choose sub-book",
        choices=[Choice(title=name, value=index) for index, name in enumerate(book_names)],
        use_indicator=True,
        use_shortcuts=False,
        style=_style(),
    ).ask()
    if selected is None:
        return None
    return BookChoice(title=book_names[int(selected)], index=int(selected))


def ask_confirm(message: str, *, default: bool = True) -> bool:
    return bool(questionary.confirm(message, default=default, style=_style()).ask())


def ask_login_recovery(message: str) -> str:
    return _select_action(
        message,
        [
            Choice(title="Try again", value=LOGIN_RETRY),
            Choice(title="Use a different email/password", value=LOGIN_DIFFERENT),
            Choice(title="Clear saved login and enter it again", value=LOGIN_CLEAR),
            Choice(title="Cancel", value=LOGIN_CANCEL),
        ],
        default=LOGIN_RETRY,
    )


def ask_runtime_recovery(message: str) -> str:
    return _select_action(
        message,
        [
            Choice(title="Try again", value=RUNTIME_RETRY),
            Choice(title="Cancel", value=RUNTIME_CANCEL),
        ],
        default=RUNTIME_RETRY,
    )


def ask_ocr_failure_action(title: str, detail: str) -> str:
    return _select_action(
        f"OCR failed for {title}: {detail}",
        [
            Choice(title="Retry OCR", value=OCR_RETRY),
            Choice(title="Save the PDF without OCR", value=OCR_KEEP_PDF),
            Choice(title="Mark this book as failed", value=OCR_FAIL),
        ],
        default=OCR_RETRY,
    )


def ask_retry_failed_books(failed_titles: list[str]) -> bool:
    if not failed_titles:
        return False
    preview = ", ".join(failed_titles[:3])
    if len(failed_titles) > 3:
        preview = f"{preview}, ..."
    return ask_confirm(f"Retry failed books now? ({preview})", default=True)


def ask_ocr_enabled(default: bool = False) -> bool:
    return ask_confirm("Add OCR/searchable text layer after export?", default=default)


def ask_ocr_profile(default: str = "balanced") -> OcrProfile:
    selected = questionary.select(
        "OCR quality/performance profile",
        choices=[
            Choice(title=profile.label, value=name)
            for name, profile in OCR_PROFILES.items()
        ],
        default=default,
        use_indicator=True,
        use_shortcuts=False,
        style=_style(),
    ).ask()
    return OCR_PROFILES.get(str(selected or default), OCR_PROFILES["balanced"])


def ask_ocr_by_book(selected: list[BookChoice], *, default: bool) -> dict[int, bool]:
    if not selected:
        return {}
    choices = [
        Choice(title=choice.title, value=choice.index, checked=default)
        for choice in selected
    ]
    enabled = questionary.checkbox(
        "Choose books that should receive OCR",
        choices=choices,
        style=_style(),
    ).ask()
    enabled_set = set(enabled or [])
    return {choice.index: choice.index in enabled_set for choice in selected}


def _select_action(message: str, choices: list[Choice], *, default: str) -> str:
    selected = questionary.select(
        message,
        choices=choices,
        default=default,
        use_indicator=True,
        use_shortcuts=False,
        style=_style(),
    ).ask()
    return str(selected or default)


def _style() -> questionary.Style:
    return questionary.Style(
        [
            ("qmark", f"fg:{THEME.accent} bold"),
            ("question", "bold"),
            ("answer", f"fg:{THEME.accent}"),
            ("pointer", f"fg:{THEME.accent} bold"),
            ("highlighted", f"fg:{THEME.accent} bold"),
            ("selected", f"fg:{THEME.success}"),
            ("instruction", f"fg:{THEME.muted}"),
        ]
    )
