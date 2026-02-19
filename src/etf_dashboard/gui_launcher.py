from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _default_reports_dir() -> Path:
    # User approved: write reports into a user-writable location.
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        return Path(local_appdata) / "etf-dashboard" / "reports"

    # Fallback if LOCALAPPDATA is missing.
    return Path.home() / "AppData" / "Local" / "etf-dashboard" / "reports"


def main() -> None:
    """Start Streamlit server and open browser.

    Notes for PyInstaller onefile:
    - We avoid importing streamlit internals here; we invoke `python -m streamlit`
      so Streamlit sets up its runtime similarly to normal usage.
    - The PyInstaller spec must include Streamlit package data (static assets).
    """

    port = _find_free_port()
    url = f"http://127.0.0.1:{port}"

    reports_dir = _default_reports_dir()
    reports_dir.mkdir(parents=True, exist_ok=True)

    # Ensure our app defaults to a safe output location when frozen.
    os.environ.setdefault("ETF_DASHBOARD_REPORT_DIR", str(reports_dir))

    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        "-m",
        "etf_dashboard.gui_streamlit",
        "--server.address=127.0.0.1",
        f"--server.port={port}",
        "--server.headless=true",
        "--browser.gatherUsageStats=false",
        "--client.showErrorDetails=false",
    ]

    # Hide Streamlit console window on Windows (user approved). PyInstaller will also
    # be built with `console=False`, but this helps if run outside that context.
    creationflags = 0
    if os.name == "nt":
        creationflags = subprocess.CREATE_NO_WINDOW  # type: ignore[attr-defined]

    proc = subprocess.Popen(
        cmd,
        cwd=str(Path.cwd()),
        creationflags=creationflags,
    )

    # Best-effort: give the server a moment to bind, then open the browser.
    time.sleep(1.0)
    webbrowser.open(url)

    # Keep the launcher alive while Streamlit is running.
    try:
        proc.wait()
    except KeyboardInterrupt:
        proc.terminate()
        raise SystemExit(0)


if __name__ == "__main__":
    main()
