from __future__ import annotations

from dataclasses import dataclass

import keyring

SERVICE_NAME = "Digi2PDF Digi4School"
EMAIL_ACCOUNT = "email"


@dataclass(frozen=True)
class StoredCredentials:
    email: str
    password: str


def load_credentials() -> StoredCredentials | None:
    try:
        email = keyring.get_password(SERVICE_NAME, EMAIL_ACCOUNT)
    except keyring.errors.KeyringError:
        return None
    if not email:
        return None
    try:
        password = keyring.get_password(SERVICE_NAME, email)
    except keyring.errors.KeyringError:
        return None
    if not password:
        return None
    return StoredCredentials(email=email, password=password)


def save_credentials(email: str, password: str) -> None:
    keyring.set_password(SERVICE_NAME, EMAIL_ACCOUNT, email)
    keyring.set_password(SERVICE_NAME, email, password)


def clear_credentials() -> None:
    try:
        email = keyring.get_password(SERVICE_NAME, EMAIL_ACCOUNT)
    except keyring.errors.KeyringError:
        email = None
    if email:
        _delete_password(email)
    _delete_password(EMAIL_ACCOUNT)


def _delete_password(account: str) -> None:
    try:
        keyring.delete_password(SERVICE_NAME, account)
    except keyring.errors.PasswordDeleteError:
        return
