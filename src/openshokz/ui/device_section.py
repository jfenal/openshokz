"""Device info section: model, firmware, battery."""

from __future__ import annotations

from typing import TYPE_CHECKING

import gi

import openshokz.core as _core
from openshokz.ui.headset import ModelData, run_async

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw, Gtk  # noqa: E402

if TYPE_CHECKING:
    from openshokz.ui.window import OpenshokzWindow

_BATTERY_ICONS = [
    "battery-empty-symbolic",
    "battery-caution-symbolic",
    "battery-low-symbolic",
    "battery-good-symbolic",
    "battery-full-symbolic",
]

_PCT_PER_ICON = 100 // len(_BATTERY_ICONS)


def _battery_icon(pct: int) -> str:
    idx = min(len(_BATTERY_ICONS) - 1, pct // _PCT_PER_ICON)
    return _BATTERY_ICONS[idx]


class DeviceSection(Adw.PreferencesGroup):
    def __init__(self, win: OpenshokzWindow) -> None:
        super().__init__()
        self.set_title("Device")
        self._win = win

        self._model_row = Adw.ActionRow()
        self._model_row.set_title("Model")
        self._model_row.set_subtitle("—")
        self.add(self._model_row)

        self._fw_row = Adw.ActionRow()
        self._fw_row.set_title("Firmware")
        self._fw_row.set_subtitle("—")
        self.add(self._fw_row)

        self._bat_row = Adw.ActionRow()
        self._bat_row.set_title("Battery")
        self._bat_row.set_subtitle("—")
        self._bat_icon = Gtk.Image.new_from_icon_name("battery-missing-symbolic")
        self._bat_row.add_prefix(self._bat_icon)
        self.add(self._bat_row)

    def _clear(self) -> None:
        for row in (self._model_row, self._fw_row, self._bat_row):
            row.set_subtitle("—")
        self._bat_icon.set_from_icon_name("battery-missing-symbolic")
        self._win.update_paired_devices([])

    def refresh(
        self,
        connected: bool,
        mac: str | None = None,
        model: ModelData | None = None,
        channel: int | None = None,
    ) -> None:
        if not connected or mac is None or model is None or channel is None:
            self._clear()
            return

        # Model name is known from the YAML without a socket connection — show immediately.
        self._model_row.set_subtitle(str(model.get("name", "—")))

        def _on_info(info: dict[str, object] | None, _error: Exception | None) -> None:
            if not info:
                for row in (self._fw_row, self._bat_row):
                    row.set_subtitle("—")
                self._bat_icon.set_from_icon_name("battery-missing-symbolic")
                return
            self._fw_row.set_subtitle(str(info.get("firmware", "—")))
            pct = info.get("battery_pct")
            raw = info.get("battery_raw")
            scale = info.get("battery_scale", 9)
            if pct is not None:
                self._bat_row.set_subtitle(f"{raw}/{scale} ({pct}%)")
                self._bat_icon.set_from_icon_name(_battery_icon(int(str(pct))))
            else:
                self._bat_row.set_subtitle("—")
            devices = list(info.get("paired_devices", []))  # type: ignore[arg-type]
            self._win.update_paired_devices(devices)

        run_async(_on_info, _core.get_headset_info, mac, model, channel)
