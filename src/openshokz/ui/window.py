"""Main application window."""

from __future__ import annotations

import gi

import openshokz.core as _core
from openshokz.ui.headset import ModelData, run_async

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw, Gtk  # noqa: E402

_DEFAULT_WIDTH = 420


class OpenshokzWindow(Adw.ApplicationWindow):
    """Settings window for openshokz headsets."""

    def __init__(self, app: Adw.Application) -> None:
        super().__init__(application=app)
        self.set_title("openshokz")
        self.set_default_size(_DEFAULT_WIDTH, -1)

        self._nav_view = Adw.NavigationView()

        main_page = Adw.NavigationPage()
        main_page.set_title("openshokz")

        toolbar_view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        toolbar_view.add_top_bar(header)

        outer_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        self._banner = Adw.Banner()
        self._banner.set_title("Headset not connected")
        self._banner.set_revealed(False)
        outer_box.append(self._banner)

        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_propagate_natural_height(True)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(600)
        clamp.set_tightening_threshold(400)

        self._content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self._content_box.set_margin_top(12)
        self._content_box.set_margin_bottom(24)
        self._content_box.set_margin_start(12)
        self._content_box.set_margin_end(12)

        clamp.set_child(self._content_box)
        scroll.set_child(clamp)
        outer_box.append(scroll)

        toolbar_view.set_content(outer_box)
        main_page.set_child(toolbar_view)
        self._nav_view.add(main_page)
        self.set_content(self._nav_view)

        self._sections: list[object] = []
        self._connection: tuple[str, ModelData, int] | None = None

    def add_section(self, group: Adw.PreferencesGroup) -> None:
        self._content_box.append(group)
        self._sections.append(group)

    def refresh_connectivity(self) -> None:
        def _on_result(result: tuple[str, ModelData, int] | None, error: Exception | None) -> None:
            connected = result is not None and error is None
            self._connection = result if connected else None
            self._banner.set_revealed(not connected)
            mac, model, channel = result if connected else (None, None, None)
            for section in self._sections:
                if hasattr(section, "refresh"):
                    section.refresh(connected, mac, model, channel)  # type: ignore[union-attr]

        run_async(_on_result, _core.resolve_headset)
