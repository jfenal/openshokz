"""Subprocess helpers for calling the openshokz CLI.

Locates shokz_config.py relative to this file so the app works without
openshokz being on PATH (development mode). In a production install the
openshokz entry point should be on PATH.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

_SUBPROCESS_TIMEOUT = 15  # seconds — long enough for 2s headset settle + command
_SCRIPT_PATH = Path(__file__).parent.parent / "shokz_config.py"


def _cli_argv() -> list[str]:
    """Return the argv prefix to invoke the openshokz CLI."""
    if shutil.which("openshokz"):
        return ["openshokz"]
    return ["python3", "-I", str(_SCRIPT_PATH)]


def run_openshokz(*args: str) -> tuple[bool, str]:
    """Run `openshokz <args>` and return (success, stdout)."""
    try:
        result = subprocess.run(
            _cli_argv() + list(args),
            capture_output=True,
            text=True,
            timeout=_SUBPROCESS_TIMEOUT,
        )
        return result.returncode == 0, result.stdout
    except Exception as exc:
        return False, str(exc)


def check_connected() -> bool:
    """Return True if the headset responds to `openshokz info`."""
    ok, _ = run_openshokz("info")
    return ok
