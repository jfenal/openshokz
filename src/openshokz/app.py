"""openshokz-app — GTK4/Adwaita settings GUI for Shokz headsets."""

from __future__ import annotations

import sys

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw  # noqa: E402

from openshokz.dbus_service import HeadsetService  # noqa: E402
from openshokz.ui.device_section import DeviceSection  # noqa: E402
from openshokz.ui.eq_section import EqSection  # noqa: E402
from openshokz.ui.language_section import LanguageSection  # noqa: E402
from openshokz.ui.window import OpenshokzWindow  # noqa: E402


class OpenshokzApp(Adw.Application):
    def __init__(self) -> None:
        super().__init__(application_id="com.github.jfenal.openshokz")
        self._win: OpenshokzWindow | None = None
        self._service = HeadsetService(
            lambda: self._win._connection if self._win is not None else None
        )
        self.connect("startup", self._on_startup)
        self.connect("activate", self._on_activate)

    def _on_startup(self, _app: Adw.Application) -> None:
        conn = self.get_dbus_connection()
        if conn is not None:
            self._service.register(conn)

    def _on_activate(self, _app: Adw.Application) -> None:
        if self._win is not None:
            self._win.present()
            return
        self._win = OpenshokzWindow(self)
        self._win.add_section(DeviceSection(self._win))
        self._win.add_section(EqSection(self._win))
        self._win.add_section(LanguageSection())
        self._win.present()
        self._win.refresh_connectivity()
        self._win.connect(
            "notify::is-active", lambda w, _: w.refresh_connectivity() if w.is_active() else None
        )

    def do_shutdown(self) -> None:
        conn = self.get_dbus_connection()
        if conn is not None:
            self._service.unregister(conn)
        Adw.Application.do_shutdown(self)


def main() -> None:
    app = OpenshokzApp()
    sys.exit(app.run(sys.argv))


if __name__ == "__main__":
    main()
