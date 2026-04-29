from __future__ import annotations

import getpass
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
    password = getpass.getpass("Digi4School password: ")
    remember = ask_confirm("Save login securely in the system keychain?", default=True)
    return (email or "").strip(), password, remember


def ask_book(book_names: list[str]) -> BookChoice | str | None:
    choices: list[Choice] = [Choice(title="Convert all books", value="all")]
    choices.extend(Choice(title=name, value=index) for index, name in enumerate(book_names))
    selected = questionary.select(
        "Choose ebook",
        choices=choices,
        use_indicator=True,
        use_shortcuts=False,
        style=_style(),
    ).ask()
    if selected is None or selected == "all":
        return selected
    return BookChoice(title=book_names[int(selected)], index=int(selected))


def ask_books(book_names: list[str]) -> list[BookChoice] | str | None:
    choices: list[Choice] = [Choice(title="Convert all books", value="all")]
    choices.extend(Choice(title=name, value=index) for index, name in enumerate(book_names))
    selected = questionary.checkbox(
        "Choose ebooks with Space, then press Enter",
        choices=choices,
        style=_style(),
    ).ask()
    if selected is None:
        return None
    if "all" in selected:
        return "all"
    return [BookChoice(title=book_names[int(index)], index=int(index)) for index in selected]


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
