"""D-Bus service: exposes headset operations to the CLI while the app is running."""

from __future__ import annotations

import json
import threading
from collections.abc import Callable

import gi

gi.require_version("Gio", "2.0")
gi.require_version("GLib", "2.0")

from gi.repository import Gio, GLib  # noqa: E402

import openshokz.core as _core  # noqa: E402
from openshokz.core import ModelData  # noqa: E402
from openshokz.dbus_iface import INTERFACE_NAME, INTERFACE_XML, OBJECT_PATH  # noqa: E402


def _to_variant(k: str, v: object) -> GLib.Variant:
    if k == "paired_devices":
        return GLib.Variant("s", json.dumps(v))
    if isinstance(v, bool):
        return GLib.Variant("b", v)
    if isinstance(v, int):
        return GLib.Variant("i", v)
    if isinstance(v, float):
        return GLib.Variant("d", v)
    return GLib.Variant("s", str(v))


def _info_to_gvariant(info: dict[str, object]) -> GLib.Variant:
    vdict = {k: _to_variant(k, v) for k, v in info.items() if v is not None}
    return GLib.Variant("(a{sv})", (vdict,))


class HeadsetService:
    """Registers a D-Bus object on the session bus while the app is running."""

    def __init__(self, get_connection: Callable[[], tuple[str, ModelData, int] | None]) -> None:
        self._get_connection = get_connection
        self._reg_id: int | None = None
        self._node_info = Gio.DBusNodeInfo.new_for_xml(INTERFACE_XML)

    def register(self, connection: Gio.DBusConnection) -> None:
        iface_info = self._node_info.lookup_interface(INTERFACE_NAME)
        self._reg_id = connection.register_object(
            OBJECT_PATH,
            iface_info,
            self._on_method_call,
            self._on_get_property,
            None,
        )

    def unregister(self, connection: Gio.DBusConnection) -> None:
        if self._reg_id is not None:
            connection.unregister_object(self._reg_id)
            self._reg_id = None

    def _on_get_property(
        self,
        connection: Gio.DBusConnection,
        sender: str,
        path: str,
        iface: str,
        name: str,
    ) -> GLib.Variant | None:
        if name == "Connected":
            return GLib.Variant("b", self._get_connection() is not None)
        return None

    def _on_method_call(
        self,
        connection: Gio.DBusConnection,
        sender: str,
        path: str,
        iface: str,
        method: str,
        params: GLib.Variant,
        invocation: Gio.DBusMethodInvocation,
    ) -> None:
        conn = self._get_connection()

        if method == "GetInfo":
            if conn is None:
                invocation.return_value(GLib.Variant("(a{sv})", ({},)))
                return
            mac, model, channel = conn

            def _run() -> None:
                try:
                    info = _core.get_headset_info(mac, model, channel)
                    GLib.idle_add(invocation.return_value, _info_to_gvariant(info))
                except Exception:
                    GLib.idle_add(invocation.return_value, GLib.Variant("(a{sv})", ({},)))

            threading.Thread(target=_run, daemon=True).start()

        elif method == "ApplyEqPreset":
            preset_arg = params.get_child_value(0).get_string()
            if conn is None:
                invocation.return_value(GLib.Variant("(b)", (False,)))
                return
            mac, model, channel = conn

            def _run() -> None:
                try:
                    ok = _core.apply_eq_preset(mac, model, channel, preset_arg)
                    GLib.idle_add(invocation.return_value, GLib.Variant("(b)", (ok,)))
                except Exception:
                    GLib.idle_add(invocation.return_value, GLib.Variant("(b)", (False,)))

            threading.Thread(target=_run, daemon=True).start()

        elif method == "ApplyLanguage":
            lang_code = params.get_child_value(0).get_string()
            if conn is None:
                invocation.return_value(GLib.Variant("(b)", (False,)))
                return
            mac, model, channel = conn

            def _run() -> None:
                try:
                    ok = _core.apply_lang_slots(mac, model, channel, [lang_code])
                    GLib.idle_add(invocation.return_value, GLib.Variant("(b)", (ok,)))
                except Exception:
                    GLib.idle_add(invocation.return_value, GLib.Variant("(b)", (False,)))

            threading.Thread(target=_run, daemon=True).start()

        else:
            invocation.return_error_literal(
                Gio.dbus_error_quark(),
                Gio.DBusError.UNKNOWN_METHOD,
                f"Unknown method: {method}",
            )
