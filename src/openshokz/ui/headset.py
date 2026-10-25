"""Direct library interface — no subprocess.

Provides async wrappers around openshokz.core for use in the GTK UI.
"""

from __future__ import annotations

import threading
from collections.abc import Callable
from typing import Any

import gi

import openshokz.core as _core

gi.require_version("GLib", "2.0")
from gi.repository import GLib  # noqa: E402

# Re-export types the UI needs
ModelData = _core.ModelData
ShokzError = _core.ShokzError


def run_async(
    callback: Callable[..., None],
    func: Callable[..., Any],
    *args: Any,
) -> None:
    """Run func(*args) in a background thread; call callback(result, error) on GLib main loop."""

    def _worker() -> None:
        try:
            result = func(*args)
            GLib.idle_add(callback, result, None)
        except Exception as exc:
            GLib.idle_add(callback, None, exc)

    threading.Thread(target=_worker, daemon=True).start()
