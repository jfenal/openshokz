"""Main application window."""

from __future__ import annotations

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw, Gtk  # noqa: E402

from ui.headset import check_connected  # noqa: E402

_DEFAULT_WIDTH = 420
_DEFAULT_HEIGHT = 600


class OpenshokzWindow(Adw.ApplicationWindow):
    """Settings window for openshokz headsets."""

    def __init__(self, app: Adw.Application) -> None:
        super().__init__(application=app)
        self.set_title("openshokz")
        self.set_default_size(_DEFAULT_WIDTH, _DEFAULT_HEIGHT)

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
        self.set_content(toolbar_view)

        self._sections: list[object] = []
        self._connected = False

    def add_section(self, group: Adw.PreferencesGroup) -> None:
        self._content_box.append(group)
        self._sections.append(group)

    def refresh_connectivity(self) -> None:
        self._connected = check_connected()
        self._banner.set_revealed(not self._connected)
        for section in self._sections:
            if hasattr(section, "refresh"):
                section.refresh(self._connected)  # type: ignore[union-attr]
