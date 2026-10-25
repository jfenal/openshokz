"""openshokz-app — GTK4/Adwaita settings GUI for Shokz headsets."""

from __future__ import annotations

import sys

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw  # noqa: E402

from openshokz.ui.device_section import DeviceSection  # noqa: E402
from openshokz.ui.eq_section import EqSection  # noqa: E402
from openshokz.ui.language_section import LanguageSection  # noqa: E402
from openshokz.ui.window import OpenshokzWindow  # noqa: E402


class OpenshokzApp(Adw.Application):
    def __init__(self) -> None:
        super().__init__(application_id="com.github.jfenal.openshokz")
        self.connect("activate", self._on_activate)

    def _on_activate(self, _app: Adw.Application) -> None:
        win = OpenshokzWindow(self)
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
