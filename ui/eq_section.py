"""EQ preset section: built-in and custom preset chips."""

from __future__ import annotations

import json
from pathlib import Path
from typing import TYPE_CHECKING

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw, Gtk  # noqa: E402

from ui.headset import run_openshokz, run_openshokz_async  # noqa: E402

if TYPE_CHECKING:
    from ui.window import OpenshokzWindow

_STATE_FILE = Path.home() / ".config" / "openshokz" / "state.json"


def _active_preset() -> str | None:
    """Return the last-applied preset arg from state.json, or None on first run."""
    try:
        return str(json.loads(_STATE_FILE.read_text()).get("active_eq", "")) or None
    except (FileNotFoundError, KeyError, ValueError, json.JSONDecodeError):
        return None


class EqSection(Adw.PreferencesGroup):
    def __init__(self, win: OpenshokzWindow) -> None:
        super().__init__()
        self.set_title("EQ Preset")
        self.set_description("Tap to switch. Active preset highlighted.")
        self._win = win
        self._connected = False
        self._active_arg: str | None = None

        self._flow_row = Adw.ActionRow()
        self._flow_row.set_activatable(False)

        self._flow = Gtk.FlowBox()
        self._flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self._flow.set_homogeneous(False)
        self._flow.set_column_spacing(6)
        self._flow.set_row_spacing(6)
        self._flow.set_margin_top(8)
        self._flow.set_margin_bottom(8)
        self._flow_row.set_child(self._flow)
        self.add(self._flow_row)

    def _rebuild_chips(self) -> None:
        while self._flow.get_first_child():
            child = self._flow.get_first_child()
            if child is not None:
                self._flow.remove(child)

        ok, out = run_openshokz("eq", "list", "--json")
        if not ok:
            return

        try:
            presets = json.loads(out)
        except json.JSONDecodeError:
            return

        active = _active_preset()
        seen_args: set[str] = set()

        for preset in presets:
            arg = str(preset.get("arg", ""))
            name = str(preset.get("name", arg))
            if arg in seen_args:
                continue
            seen_args.add(arg)

            btn = Gtk.ToggleButton(label=name)
            btn.add_css_class("pill")
            if active and arg.lower() == active.lower():
                btn.set_active(True)
                btn.add_css_class("suggested-action")
            btn.connect("toggled", self._on_chip_toggled, arg, preset)
            btn.set_sensitive(self._connected)
            self._flow.append(btn)

        if len([p for p in presets if not p.get("builtin")]) < 3:
            add_btn = Gtk.Button(label="+ Add")
            add_btn.add_css_class("pill")
            add_btn.set_sensitive(self._connected)
            add_btn.connect("clicked", self._on_add_clicked)
            self._flow.append(add_btn)

    def _on_chip_toggled(self, btn: Gtk.ToggleButton, arg: str, _preset: dict[str, object]) -> None:
        if not btn.get_active():
            return
        btn.set_sensitive(False)  # prevent double-click during 3 s headset call

        def _done(ok: bool, _out: str) -> None:
            btn.set_sensitive(self._connected)
            if ok:
                self._active_arg = arg
                self._rebuild_chips()
            else:
                btn.set_active(False)

        run_openshokz_async(_done, "eq", arg)

    def _on_add_clicked(self, _: Gtk.Button) -> None:
        from ui.edit_preset_page import EditPresetPage

        nav = self._find_nav()
        if nav is None:
            return
        page = EditPresetPage(on_done=self._on_edit_done, is_new=True)
        nav.push(page)

    def _find_nav(self) -> Adw.NavigationView | None:
        for attr in ("_nav_view", "_navigation_view"):
            nav = getattr(self._win, attr, None)
            if nav is not None:
                return nav
        return None

    def _on_edit_done(self) -> None:
        nav = self._find_nav()
        if nav:
            nav.pop()
        self._rebuild_chips()

    def refresh(self, connected: bool) -> None:
        self._connected = connected
        self._rebuild_chips()
