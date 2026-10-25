"""D-Bus client: delegates CLI operations to the running app when available."""

from __future__ import annotations

import json

import gi

gi.require_version("Gio", "2.0")
gi.require_version("GLib", "2.0")

from gi.repository import Gio, GLib  # noqa: E402

from openshokz.dbus_iface import BUS_NAME, INTERFACE_NAME, OBJECT_PATH  # noqa: E402

_TIMEOUT_SHORT = 5_000  # ms — GetInfo handshake
_TIMEOUT_LONG = 15_000  # ms — EQ/lang apply (headset handshake)


def get_proxy() -> Gio.DBusProxy | None:
    """Return a synchronous D-Bus proxy to the running app, or None if not running."""
    try:
        proxy = Gio.DBusProxy.new_for_bus_sync(
            Gio.BusType.SESSION,
            Gio.DBusProxyFlags.DO_NOT_AUTO_START,
            None,
            BUS_NAME,
            OBJECT_PATH,
            INTERFACE_NAME,
            None,
        )
        return proxy if proxy.get_name_owner() else None
    except Exception:
        return None


def proxy_get_info(proxy: Gio.DBusProxy) -> dict[str, object] | None:
    try:
        result = proxy.call_sync("GetInfo", None, Gio.DBusCallFlags.NONE, _TIMEOUT_SHORT, None)
        if not result:
            return None
        raw: dict[str, object] = dict(result[0])
        if not raw:
            return None
        # Unpack GLib.Variant values; paired_devices is JSON-encoded string.
        info: dict[str, object] = {}
        for k, v in raw.items():
            val = v.unpack() if isinstance(v, GLib.Variant) else v
            info[k] = json.loads(val) if k == "paired_devices" and isinstance(val, str) else val
        return info
    except Exception:
        return None


def proxy_apply_eq(proxy: Gio.DBusProxy, preset_arg: str) -> bool:
    try:
        result = proxy.call_sync(
            "ApplyEqPreset",
            GLib.Variant("(s)", (preset_arg,)),
            Gio.DBusCallFlags.NONE,
            _TIMEOUT_LONG,
            None,
        )
        return bool(result[0]) if result else False
    except Exception:
        return False


def proxy_apply_language(proxy: Gio.DBusProxy, lang_code: str) -> bool:
    try:
        result = proxy.call_sync(
            "ApplyLanguage",
            GLib.Variant("(s)", (lang_code,)),
            Gio.DBusCallFlags.NONE,
            _TIMEOUT_LONG,
            None,
        )
        return bool(result[0]) if result else False
    except Exception:
        return False
