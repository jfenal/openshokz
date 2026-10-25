"""Main application window."""

from __future__ import annotations

from typing import TYPE_CHECKING

import gi

import openshokz.core as _core
from openshokz.ui.headset import ModelData, run_async

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw, Gio, GLib, Gtk  # noqa: E402

if TYPE_CHECKING:
    from openshokz.ui.eq_section import EqSection

_DEFAULT_WIDTH = 640
_MIN_HEIGHT = 600


class OpenshokzWindow(Adw.ApplicationWindow):
    """Settings window for openshokz headsets."""

    def __init__(self, app: Adw.Application) -> None:
        super().__init__(application=app)
        self.set_title("openshokz")
        self.set_default_size(_DEFAULT_WIDTH, _MIN_HEIGHT)
        self.set_size_request(420, _MIN_HEIGHT)

        toolbar_view = Adw.ToolbarView()
        header = Adw.HeaderBar()

        # Hamburger menu button — model is replaced on each preset change
        self._menu_btn = Gtk.MenuButton()
        self._menu_btn.set_icon_name("open-menu-symbolic")
        header.pack_end(self._menu_btn)

        toolbar_view.add_top_bar(header)

        # String-parameter actions for Edit/Delete individual presets
        str_type = GLib.VariantType.new("s")
        for action_name, handler in (
            ("edit-preset", self._on_edit_preset),
            ("delete-preset", self._on_delete_preset),
        ):
            act = Gio.SimpleAction.new(action_name, str_type)
            act.connect("activate", handler)
            self.add_action(act)

        # No-parameter action for Add
        add_act = Gio.SimpleAction.new("add-preset", None)
        add_act.connect("activate", self._on_add_preset)
        self.add_action(add_act)

        # --- Sidebar (Paired Devices) ---
        sidebar_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        sidebar_box.set_margin_top(12)
        sidebar_box.set_margin_bottom(12)
        sidebar_box.set_margin_start(12)
        sidebar_box.set_margin_end(12)

        sidebar_title = Gtk.Label(label="Paired Devices")
        sidebar_title.add_css_class("heading")
        sidebar_title.set_halign(Gtk.Align.START)
        sidebar_title.set_margin_bottom(8)
        sidebar_box.append(sidebar_title)

        self._devices_placeholder = Gtk.Label(label="—")
        self._devices_placeholder.add_css_class("dim-label")
        self._devices_placeholder.set_halign(Gtk.Align.START)
        sidebar_box.append(self._devices_placeholder)

        self._devices_listbox = Gtk.ListBox()
        self._devices_listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        self._devices_listbox.add_css_class("boxed-list")
        self._devices_listbox.set_visible(False)
        sidebar_box.append(self._devices_listbox)

        sidebar_scroll = Gtk.ScrolledWindow()
        sidebar_scroll.set_vexpand(True)
        sidebar_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sidebar_scroll.set_child(sidebar_box)

        # --- Main content ---
        outer_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)

        self._banner = Adw.Banner()
        self._banner.set_title("Headset not connected")
        self._banner.set_revealed(False)
        outer_box.append(self._banner)

        content_scroll = Gtk.ScrolledWindow()
        content_scroll.set_vexpand(True)
        content_scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        content_scroll.set_propagate_natural_height(True)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(600)
        clamp.set_tightening_threshold(400)

        self._content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        self._content_box.set_margin_top(12)
        self._content_box.set_margin_bottom(24)
        self._content_box.set_margin_start(12)
        self._content_box.set_margin_end(12)

        clamp.set_child(self._content_box)
        content_scroll.set_child(clamp)
        outer_box.append(content_scroll)

        # --- Split view ---
        self._split_view = Adw.OverlaySplitView()
        self._split_view.set_sidebar_position(Gtk.PackType.END)
        self._split_view.set_min_sidebar_width(200)
        self._split_view.set_max_sidebar_width(240)
        self._split_view.set_collapsed(False)
        self._split_view.set_show_sidebar(True)
        self._split_view.set_content(outer_box)
        self._split_view.set_sidebar(sidebar_scroll)

        toolbar_view.set_content(self._split_view)
        self.set_content(toolbar_view)

        self._sections: list[object] = []
        self._connection: tuple[str, ModelData, int] | None = None
        self._refreshing = False
        self._eq_section: EqSection | None = None

        # Build the initial (empty) menu
        self.rebuild_preset_menu([])

    def add_section(self, group: Adw.PreferencesGroup) -> None:
        from openshokz.ui.eq_section import EqSection

        self._content_box.append(group)
        self._sections.append(group)
        if isinstance(group, EqSection):
            self._eq_section = group

    def update_paired_devices(self, devices: list[dict]) -> None:
        """Populate the sidebar with paired device rows; show/hide it accordingly."""
        while self._devices_listbox.get_first_child():
            child = self._devices_listbox.get_first_child()
            if child is not None:
                self._devices_listbox.remove(child)

        for dev in devices:
            assert isinstance(dev, dict)
            status = "connected" if dev.get("active") else "paired"
            row = Adw.ActionRow()
            row.set_title(str(dev.get("name", "?")))
            row.set_subtitle(f"[{status}]  {dev.get('mac', '?')}")
            self._devices_listbox.append(row)

        self._devices_placeholder.set_visible(not bool(devices))
        self._devices_listbox.set_visible(bool(devices))

    def rebuild_preset_menu(self, custom_presets: list[dict]) -> None:
        """Rebuild the header bar menu from the current custom preset list."""
        menu = Gio.Menu()

        if custom_presets:
            presets_section = Gio.Menu()
            for p in custom_presets:
                arg = str(p.get("name", ""))
                label = arg
                preset_submenu = Gio.Menu()
                preset_submenu.append(f"Edit “{label}”", f"win.edit-preset::{arg}")
                preset_submenu.append(f"Delete “{label}”", f"win.delete-preset::{arg}")
                item = Gio.MenuItem.new_submenu(label, preset_submenu)
                presets_section.append_item(item)
            menu.append_section("Custom Presets", presets_section)

        add_item = Gio.MenuItem.new("Add Preset", "win.add-preset")
        add_section = Gio.Menu()
        add_section.append_item(add_item)
        menu.append_section(None, add_section)

        add_act = self.lookup_action("add-preset")
        if add_act:
            add_act.set_enabled(len(custom_presets) < 3)

        self._menu_btn.set_menu_model(menu)

    def _on_edit_preset(self, _action: Gio.SimpleAction, param: GLib.Variant) -> None:
        if self._eq_section is not None:
            self._eq_section.open_edit(param.get_string())

    def _on_delete_preset(self, _action: Gio.SimpleAction, param: GLib.Variant) -> None:
        if self._eq_section is not None:
            self._eq_section.delete_preset(param.get_string())

    def _on_add_preset(self, _action: Gio.SimpleAction, _param: object) -> None:
        if self._eq_section is not None:
            self._eq_section.open_add()

    def refresh_connectivity(self) -> None:
        if self._refreshing:
            return
        self._refreshing = True

        def _on_result(result: tuple[str, ModelData, int] | None, error: Exception | None) -> None:
            self._refreshing = False
            connected = result is not None and error is None
            self._connection = result if connected else None
            self._banner.set_revealed(not connected)
            mac, model, channel = result if connected else (None, None, None)
            for section in self._sections:
                if hasattr(section, "refresh"):
                    section.refresh(connected, mac, model, channel)  # type: ignore[union-attr]

        run_async(_on_result, _core.resolve_headset)
