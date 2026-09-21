from __future__ import annotations

import logging
import socket
import threading
import webbrowser

import uvicorn

from jd_capital.app import app
from jd_capital.config import APP_NAME, PORT, get_data_dir


def free_port(preferred: int) -> int:
    for port in range(preferred, preferred + 20):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("127.0.0.1", port))
                return port
            except OSError:
                continue
    raise RuntimeError("No se encontró un puerto local disponible para JD Capital.")


def configure_logging() -> None:
    log_file = get_data_dir() / "jd_capital.log"
    logging.basicConfig(
        filename=str(log_file),
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        encoding="utf-8",
        force=True,
    )
    logging.getLogger(APP_NAME).info("Inicio de JD Capital")


def run_server(port: int) -> None:
    """Run Uvicorn without its console-oriented logging configuration.

    A PyInstaller ``--windowed`` executable has no stdout/stderr streams.  The
    Uvicorn default logging config inspects those streams with ``isatty()``, so
    JD Capital owns logging and routes all server messages to jd_capital.log.
    """
    uvicorn.run(
        app,
        host="127.0.0.1",
        port=port,
        log_level="warning",
        log_config=None,
        access_log=False,
    )


if __name__ == "__main__":
    configure_logging()
    port = free_port(PORT)
    threading.Timer(0.8, lambda: webbrowser.open(f"http://127.0.0.1:{port}/")).start()
    run_server(port)
