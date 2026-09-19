from __future__ import annotations

import os
import secrets
from pathlib import Path

from .config import get_data_dir


def get_session_secret() -> str:
    env = os.getenv("JD_SESSION_SECRET", "").strip()
    if env:
        return env
    path = get_data_dir() / "session.secret"
    try:
        if path.exists():
            value = path.read_text(encoding="utf-8").strip()
            if len(value) >= 32:
                return value
        value = secrets.token_urlsafe(48)
        path.write_text(value, encoding="utf-8")
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        return value
    except OSError:
        # Last-resort in-memory secret; sessions will simply be invalidated on restart.
        return secrets.token_urlsafe(48)
