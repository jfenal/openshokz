"""Edit-preset navigation page for custom EQ presets."""

from __future__ import annotations

from collections.abc import Callable

import gi

import openshokz.core as _core
from openshokz.ui.headset import ModelData, run_async

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw, Gtk  # noqa: E402

BAND_LABELS = ["250 Hz", "500 Hz", "1 kHz", "2 kHz", "4 kHz", "6 kHz", "8 kHz"]


class EditPresetPage(Adw.NavigationPage):
    """Page for creating or editing a custom EQ preset."""

    def __init__(
        self,
        on_done: Callable[[], None],
        connection: tuple[str, ModelData, int] | None = None,
        name: str = "",
        bands: list[int] | None = None,
        is_new: bool = True,
    ) -> None:
        super().__init__()
        self.set_title("Edit Preset" if not is_new else "New Preset")
        self._on_done = on_done
        self._is_new = is_new
        self._original_name = name
        self._connection = connection

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=12)
        box.set_margin_top(12)
        box.set_margin_bottom(24)
        box.set_margin_start(12)
        box.set_margin_end(12)

        name_group = Adw.PreferencesGroup()
        name_group.set_title("Preset name")
        self._name_entry = Adw.EntryRow()
        self._name_entry.set_title("Name")
        self._name_entry.set_text(name)
        name_group.add(self._name_entry)
        box.append(name_group)

        bands_group = Adw.PreferencesGroup()
        bands_group.set_title("EQ bands (dB)")
        self._scales: list[Gtk.Scale] = []
        init_bands = bands or [0] * 7
        for i, label in enumerate(BAND_LABELS):
            row = Adw.ActionRow()
            row.set_title(label)
            scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, -12, 12, 1)
            scale.set_value(init_bands[i])
            scale.set_hexpand(True)
            scale.set_draw_value(True)
            scale.set_size_request(160, -1)
            row.add_suffix(scale)
            self._scales.append(scale)
            bands_group.add(row)
        box.append(bands_group)

        actions_group = Adw.PreferencesGroup()
        apply_row = Adw.ButtonRow()
        apply_row.set_title("Apply & Save")
        apply_row.add_css_class("suggested-action")
        apply_row.connect("activated", self._on_apply)
        actions_group.add(apply_row)

        if not is_new:
            delete_row = Adw.ButtonRow()
            delete_row.set_title("Delete")
            delete_row.add_css_class("destructive-action")
            delete_row.connect("activated", self._on_delete)
            actions_group.add(delete_row)

        box.append(actions_group)

        clamp = Adw.Clamp()
        clamp.set_child(box)
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        scroll.set_child(clamp)
        self.set_child(scroll)

    def _current_bands(self) -> list[int]:
        return [int(s.get_value()) for s in self._scales]

    def _on_apply(self, _: Adw.ButtonRow) -> None:
        name = self._name_entry.get_text().strip()
        if not name:
            return
        bands = self._current_bands()
        try:
            _core.add_custom_preset(name, bands)
        except _core.ShokzError:
            return

        if self._connection:
            mac, model, channel = self._connection

            def _done(_result: object, _error: object) -> None:
                self._on_done()

            run_async(_done, _core.apply_eq_preset, mac, model, channel, name)
        else:
            self._on_done()

    def _on_delete(self, _: Adw.ButtonRow) -> None:
        try:
            _core.delete_custom_preset(self._original_name)
        except _core.ShokzError:
            return
        self._on_done()
