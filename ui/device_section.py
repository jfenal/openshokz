"""Device info section: firmware, battery, paired devices."""

from __future__ import annotations

import gi

gi.require_version("Adw", "1")
gi.require_version("Gtk", "4.0")

from gi.repository import Adw  # noqa: E402

from ui.headset import run_openshokz  # noqa: E402

_BATTERY_ICONS = [
    "battery-empty-symbolic",
    "battery-caution-symbolic",
    "battery-low-symbolic",
    "battery-good-symbolic",
    "battery-full-symbolic",
]


_PCT_PER_ICON = 100 // len(_BATTERY_ICONS)  # 20 — each icon covers 20% range


def _battery_icon(pct: int) -> str:
    idx = min(len(_BATTERY_ICONS) - 1, pct // _PCT_PER_ICON)
    return _BATTERY_ICONS[idx]


def _parse_info(text: str) -> dict[str, str]:
    result: dict[str, str] = {}
    devices: list[str] = []
    in_devices = False
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("Model"):
            result["model"] = line.split(":", 1)[1].strip()
        elif line.startswith("Firmware"):
            result["firmware"] = line.split(":", 1)[1].strip()
        elif line.startswith("Battery"):
            result["battery"] = line.split(":", 1)[1].strip()
        elif "Paired devices" in line or ("Connected" in line and ":" in line):
            in_devices = True
        elif in_devices and line.startswith("["):
            devices.append(line)
    if devices:
        result["devices"] = "\n".join(devices)
    return result


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
        self.add(self._bat_row)

        self._dev_row = Adw.ActionRow()
        self._dev_row.set_title("Paired devices")
        self._dev_row.set_subtitle("—")
        self._dev_row.set_subtitle_lines(6)
        self.add(self._dev_row)

    def refresh(self, connected: bool) -> None:
        if not connected:
            for row in (self._model_row, self._fw_row, self._bat_row, self._dev_row):
                row.set_subtitle("—")
            return

        ok, text = run_openshokz("info")
        if not ok:
            return
        info = _parse_info(text)
        self._model_row.set_subtitle(info.get("model", "—"))
        self._fw_row.set_subtitle(info.get("firmware", "—"))
        bat = info.get("battery", "—")
        self._bat_row.set_subtitle(bat)
        self._dev_row.set_subtitle(info.get("devices", "—"))
