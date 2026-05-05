from __future__ import annotations

from digi2pdf import credentials


def test_save_credentials_removes_previous_account_password(monkeypatch) -> None:
    store = {
        (credentials.SERVICE_NAME, credentials.EMAIL_ACCOUNT): "old@example.com",
        (credentials.SERVICE_NAME, "old@example.com"): "old-password",
    }

    monkeypatch.setattr(
        credentials.keyring,
        "get_password",
        lambda service, account: store.get((service, account)),
    )
    monkeypatch.setattr(
        credentials.keyring,
        "set_password",
        lambda service, account, password: store.__setitem__((service, account), password),
    )
    monkeypatch.setattr(
        credentials.keyring,
        "delete_password",
        lambda service, account: store.pop((service, account)),
    )

    credentials.save_credentials("new@example.com", "new-password")

    assert (credentials.SERVICE_NAME, "old@example.com") not in store
    assert store[(credentials.SERVICE_NAME, credentials.EMAIL_ACCOUNT)] == "new@example.com"
    assert store[(credentials.SERVICE_NAME, "new@example.com")] == "new-password"
