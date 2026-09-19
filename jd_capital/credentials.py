from __future__ import annotations

import getpass
import os

SERVICE_NAME = "JD Capital"
ACCOUNT_NAME = f"openai:{getpass.getuser()}"


def get_openai_api_key() -> str:
    env = os.getenv("OPENAI_API_KEY", "").strip()
    if env:
        return env
    try:
        import keyring
        return (keyring.get_password(SERVICE_NAME, ACCOUNT_NAME) or "").strip()
    except Exception:
        return ""


def set_openai_api_key(value: str) -> None:
    value = (value or "").strip()
    if not value:
        delete_openai_api_key()
        return
    import keyring
    keyring.set_password(SERVICE_NAME, ACCOUNT_NAME, value)


def delete_openai_api_key() -> None:
    try:
        import keyring
        keyring.delete_password(SERVICE_NAME, ACCOUNT_NAME)
    except Exception:
        pass
