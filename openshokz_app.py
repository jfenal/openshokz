#!/usr/bin/env python3 -I
"""openshokz-app — GTK4/Adwaita settings GUI for Shokz headsets.

Usage:
  python3 -I openshokz_app.py
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw  # noqa: E402

from ui.device_section import DeviceSection  # noqa: E402
from ui.eq_section import EqSection  # noqa: E402
from ui.language_section import LanguageSection  # noqa: E402
from ui.window import OpenshokzWindow  # noqa: E402


class OpenshokzApp(Adw.Application):
    def __init__(self) -> None:
        super().__init__(application_id="com.github.jfenal.openshokz")
        self.connect("activate", self._on_activate)

    def _on_activate(self, app: Adw.Application) -> None:
        if not shutil.which("openshokz"):
            script = Path(__file__).parent / "shokz_config.py"
            if not script.exists():
                dialog = Adw.AlertDialog()
                dialog.set_heading("openshokz not found")
                dialog.set_body(
                    "Could not find the openshokz CLI. "
                    "Make sure shokz_config.py is in the same directory."
                )
                dialog.add_response("ok", "OK")
                dialog.present(None)
                return

        win = OpenshokzWindow(app)
        win.add_section(DeviceSection())
        win.add_section(EqSection(win))
        win.add_section(LanguageSection())
        win.present()
        win.refresh_connectivity()
        win.connect("notify::is-active", lambda w, _: w.refresh_connectivity())


def main() -> None:
    app = OpenshokzApp()
    sys.exit(app.run(sys.argv))


if __name__ == "__main__":
    main()
