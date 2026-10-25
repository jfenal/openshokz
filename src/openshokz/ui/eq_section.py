"""EQ preset section: built-in and custom preset chips."""

from __future__ import annotations

from typing import TYPE_CHECKING

import openshokz.core as _core
from openshokz.ui.headset import ModelData, run_async

if TYPE_CHECKING:
    from openshokz.ui.window import OpenshokzWindow

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw, Gtk  # noqa: E402


def _active_preset() -> str | None:
    return _core.load_state().get("active_eq") or None


class EqSection(Adw.PreferencesGroup):
    def __init__(self, win: OpenshokzWindow) -> None:
        super().__init__()
        self.set_title("EQ Preset")
        self.set_description("Tap to switch. Active preset highlighted.")
        self._win = win
        self._connection: tuple[str, ModelData, int] | None = None

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

        # Load presets immediately — no headset needed
        self._load_preset_chips()

    def _load_preset_chips(self) -> None:
        def _on_presets(result: list[dict[str, object]] | None, _error: Exception | None) -> None:
            while self._flow.get_first_child():
                child = self._flow.get_first_child()
                if child is not None:
                    self._flow.remove(child)
            if not result:
                return

            active = _active_preset()
            seen: set[str] = set()
            connected = self._connection is not None

            for preset in result:
                arg = str(preset.get("arg", ""))
                name = str(preset.get("name", arg))
                if arg in seen:
                    continue
                seen.add(arg)

                btn = Gtk.ToggleButton(label=name)
                btn.add_css_class("pill")
                if active and arg.lower() == active.lower():
                    btn.set_active(True)
                    btn.add_css_class("suggested-action")
                btn.connect("toggled", self._on_chip_toggled, arg)
                btn.set_sensitive(connected)
                self._flow.append(btn)

            custom_count = sum(1 for p in result if not p.get("builtin"))
            if custom_count < 3:
                add_btn = Gtk.Button(label="+ Add")
                add_btn.add_css_class("pill")
                add_btn.set_sensitive(connected)
                add_btn.connect("clicked", self._on_add_clicked)
                self._flow.append(add_btn)

        run_async(_on_presets, _core.list_eq_presets)

    def _update_chip_sensitivity(self, sensitive: bool) -> None:
        child = self._flow.get_first_child()
        while child is not None:
            widget = child.get_child() if hasattr(child, "get_child") else child
            if widget is not None:
                widget.set_sensitive(sensitive)
            child = child.get_next_sibling()

    def _on_chip_toggled(self, btn: Gtk.ToggleButton, arg: str) -> None:
        if not btn.get_active():
            return
        if self._connection is None:
            btn.set_active(False)
            return
        mac, model, channel = self._connection
        btn.set_sensitive(False)

        def _done(ok: bool | None, _error: Exception | None) -> None:
            btn.set_sensitive(self._connection is not None)
            if ok:
                self._load_preset_chips()
            else:
                btn.set_active(False)

        run_async(_done, _core.apply_eq_preset, mac, model, channel, arg)

    def _on_add_clicked(self, _: Gtk.Button) -> None:
        from openshokz.ui.edit_preset_page import EditPresetPage

        nav = getattr(self._win, "_nav_view", None)
        if nav is None:
            return
        page = EditPresetPage(
            on_done=self._on_edit_done,
            connection=self._connection,
            is_new=True,
        )
        nav.push(page)

    def _on_edit_done(self) -> None:
        nav = getattr(self._win, "_nav_view", None)
        if nav:
            nav.pop()
        self._load_preset_chips()

    def refresh(
        self,
        connected: bool,
        mac: str | None = None,
        model: ModelData | None = None,
        channel: int | None = None,
    ) -> None:
        self._connection = (
            (mac, model, channel) if connected and mac and model and channel else None
        )  # type: ignore[assignment]
        self._update_chip_sensitivity(connected)
