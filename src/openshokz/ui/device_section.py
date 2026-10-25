"""Device info section: firmware, battery, paired devices."""

from __future__ import annotations

import gi

import openshokz.core as _core
from openshokz.ui.headset import ModelData, run_async

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw, Gtk  # noqa: E402

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
    def __init__(self) -> None:
        super().__init__()
        self.set_title("Device")

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

        self._dev_row = Adw.ActionRow()
        self._dev_row.set_title("Paired devices")
        self._dev_row.set_subtitle("—")
        self._dev_row.set_subtitle_lines(6)
        self.add(self._dev_row)

    def _clear(self) -> None:
        for row in (self._model_row, self._fw_row, self._bat_row, self._dev_row):
            row.set_subtitle("—")
        self._bat_icon.set_from_icon_name("battery-missing-symbolic")

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

        def _on_info(info: dict[str, object] | None, _error: Exception | None) -> None:
            if not info:
                self._clear()
                return
            self._model_row.set_subtitle(str(info.get("name", "—")))
            self._fw_row.set_subtitle(str(info.get("firmware", "—")))
            pct = info.get("battery_pct")
            raw = info.get("battery_raw")
            scale = info.get("battery_scale", 9)
            if pct is not None:
                self._bat_row.set_subtitle(f"{raw}/{scale} ({pct}%)")
                self._bat_icon.set_from_icon_name(_battery_icon(int(str(pct))))
            else:
                self._bat_row.set_subtitle("—")
            devices = info.get("paired_devices", [])
            if devices:
                lines = []
                for dev in devices:  # type: ignore[union-attr]
                    assert isinstance(dev, dict)
                    status = "connected" if dev.get("active") else "paired"
                    lines.append(f"[{status}] {dev.get('name', '?')} ({dev.get('mac', '?')})")
                self._dev_row.set_subtitle("\n".join(lines))
            else:
                self._dev_row.set_subtitle("—")

        run_async(_on_info, _core.get_headset_info, mac, model, channel)
