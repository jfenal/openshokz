"""openshokz.core — shared library for CLI and GUI.

All functions return data structures; none print to stdout.
"""

from __future__ import annotations

import contextlib
import json
import socket
import struct
import subprocess
from datetime import datetime
from pathlib import Path
from typing import TypedDict, cast

import yaml

from openshokz.protocol import (
    CMD_FIRMWARE,
    DEFAULT_CHANNEL,
    RESPONSE_BIT,
    build_packet,
    connect,
    drain,
)


class ShokzError(Exception):
    """User-facing configuration error."""


# ---------------------------------------------------------------------------
# TypedDicts
# ---------------------------------------------------------------------------


class EqPreset(TypedDict, total=False):
    id: int
    bands: list[int]
    label: str


class EqConfig(TypedDict, total=False):
    command: int
    preset_id_byte: int
    band_bytes: list[int]
    band_frequencies: list[int]
    presets: dict[str, EqPreset]
    custom_preset_id: int


class BatteryConfig(TypedDict, total=False):
    command: int
    scale: int


class SimpleCommand(TypedDict, total=False):
    command: int


class LanguageConfig(TypedDict, total=False):
    command: int
    codes: dict[str, int]


class BluetoothConfig(TypedDict, total=False):
    rfcomm_channel: int


class MultipointConfig(TypedDict, total=False):
    add_command: int
    primary_command: int


class ModelData(TypedDict, total=False):
    name: str
    firmware_prefix: str
    oui_prefixes: list[str]
    bluetooth: BluetoothConfig
    battery: BatteryConfig
    eq: EqConfig
    language: LanguageConfig
    device_info: SimpleCommand
    multipoint: MultipointConfig


# ---------------------------------------------------------------------------
# Coerce helpers
# ---------------------------------------------------------------------------


def _as_dict(v: object) -> dict[str, object]:
    if isinstance(v, dict):
        return {str(k): val for k, val in cast(dict[object, object], v).items()}
    return {}


def _as_list(v: object) -> list[object]:
    if isinstance(v, list):
        return cast(list[object], v)
    return []


def _as_int(v: object, default: int = 0) -> int:
    if isinstance(v, int):
        return v
    try:
        return int(cast(str, v))
    except (TypeError, ValueError):
        return default


def _as_str(v: object, default: str = "") -> str:
    return str(v) if v is not None else default


def _coerce_eq(eq: dict[str, object]) -> EqConfig:
    ec: EqConfig = {}
    if "command" in eq:
        ec["command"] = _as_int(eq["command"])
    if "preset_id_byte" in eq:
        ec["preset_id_byte"] = _as_int(eq["preset_id_byte"])
    if "band_bytes" in eq:
        ec["band_bytes"] = [_as_int(x) for x in _as_list(eq["band_bytes"])]
    if "band_frequencies" in eq:
        ec["band_frequencies"] = [_as_int(x) for x in _as_list(eq["band_frequencies"])]
    if "custom_preset_id" in eq:
        ec["custom_preset_id"] = _as_int(eq["custom_preset_id"], 1)
    if "presets" in eq:
        raw_presets = _as_dict(eq["presets"])
        presets: dict[str, EqPreset] = {}
        for key, val in raw_presets.items():
            pdict = _as_dict(val)
            ep: EqPreset = {}
            if "id" in pdict:
                ep["id"] = _as_int(pdict["id"], 1)
            if "bands" in pdict:
                ep["bands"] = [_as_int(x) for x in _as_list(pdict["bands"])]
            if "label" in pdict:
                ep["label"] = _as_str(pdict["label"])
            presets[key] = ep
        ec["presets"] = presets
    return ec


def _coerce_language(lang: dict[str, object]) -> LanguageConfig:
    lc: LanguageConfig = {}
    if "command" in lang:
        lc["command"] = _as_int(lang["command"])
    if "codes" in lang:
        lc["codes"] = {k: _as_int(v) for k, v in _as_dict(lang["codes"]).items()}
    return lc


def _coerce_battery(bat: dict[str, object]) -> BatteryConfig:
    bc: BatteryConfig = {}
    if "command" in bat:
        bc["command"] = _as_int(bat["command"])
    if "scale" in bat:
        bc["scale"] = _as_int(bat["scale"], 9)
    return bc


def _coerce_multipoint(mp: dict[str, object]) -> MultipointConfig:
    mpc: MultipointConfig = {}
    if "add_command" in mp:
        mpc["add_command"] = _as_int(mp["add_command"])
    if "primary_command" in mp:
        mpc["primary_command"] = _as_int(mp["primary_command"])
    return mpc


def _coerce_model(raw: object) -> ModelData:
    if not isinstance(raw, dict):
        raise ValueError("Model file must be a YAML mapping")
    d = _as_dict(raw)
    m: ModelData = {}

    if "name" in d:
        m["name"] = _as_str(d["name"])
    if "firmware_prefix" in d:
        m["firmware_prefix"] = _as_str(d["firmware_prefix"])
    if "oui_prefixes" in d:
        m["oui_prefixes"] = [_as_str(x) for x in _as_list(d["oui_prefixes"])]

    if "bluetooth" in d:
        bt = _as_dict(d["bluetooth"])
        btc: BluetoothConfig = {}
        if "rfcomm_channel" in bt:
            btc["rfcomm_channel"] = _as_int(bt["rfcomm_channel"], DEFAULT_CHANNEL)
        m["bluetooth"] = btc

    if "battery" in d:
        m["battery"] = _coerce_battery(_as_dict(d["battery"]))
    if "eq" in d:
        m["eq"] = _coerce_eq(_as_dict(d["eq"]))
    if "language" in d:
        m["language"] = _coerce_language(_as_dict(d["language"]))

    if "device_info" in d:
        di = _as_dict(d["device_info"])
        sc: SimpleCommand = {}
        if "command" in di:
            sc["command"] = _as_int(di["command"])
        m["device_info"] = sc

    if "multipoint" in d:
        m["multipoint"] = _coerce_multipoint(_as_dict(d["multipoint"]))

    return m


# ---------------------------------------------------------------------------
# Model loading
# ---------------------------------------------------------------------------


def _models_dir() -> Path:
    return Path(__file__).parent / "models"


def _load_model(path: Path) -> ModelData:
    with open(path) as f:
        raw: object = yaml.safe_load(f)
    return _coerce_model(raw)


def _find_model_by_prefix(firmware: str) -> ModelData | None:
    for yaml_path in _models_dir().glob("*.yaml"):
        with contextlib.suppress(Exception):
            m = _load_model(yaml_path)
            prefix = m.get("firmware_prefix", "")
            if prefix and firmware.startswith(prefix):
                return m
    return None


def list_models() -> list[ModelData]:
    """Return all model definitions from the models directory."""
    models: list[ModelData] = []
    for yaml_path in sorted(_models_dir().glob("*.yaml")):
        with contextlib.suppress(Exception):
            models.append(_load_model(yaml_path))
    return models


def default_model() -> ModelData:
    """Return the first available model definition."""
    models = list_models()
    if not models:
        raise ShokzError("No model definitions found in models/")
    return models[0]


def _load_model_by_name(model_name: str) -> ModelData:
    path = _models_dir() / model_name
    if not path.exists():
        path = _models_dir() / f"{model_name}.yaml"
    if not path.exists():
        raise ShokzError(f"Model file not found: {model_name}")
    return _load_model(path)


# ---------------------------------------------------------------------------
# Config / state persistence
# ---------------------------------------------------------------------------


def _config_dir() -> Path:
    d = Path.home() / ".config" / "openshokz"
    d.mkdir(parents=True, exist_ok=True)
    return d


def load_custom_presets() -> list[dict[str, object]]:
    """Read custom presets from presets.json; return [] if absent."""
    path = _config_dir() / "presets.json"
    if not path.exists():
        return []
    return list(json.loads(path.read_text()))


def save_custom_presets(presets: list[dict[str, object]]) -> None:
    """Atomically write custom presets to presets.json."""
    path = _config_dir() / "presets.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(presets, indent=2))
    tmp.rename(path)


def load_state() -> dict[str, str]:
    """Read state.json; return {} if absent."""
    path = _config_dir() / "state.json"
    if not path.exists():
        return {}
    return dict(json.loads(path.read_text()))


def save_state(active_eq: str) -> None:
    """Atomically write active EQ preset name to state.json."""
    path = _config_dir() / "state.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"active_eq": active_eq, "updated": datetime.now().isoformat()}))
    tmp.rename(path)


# ---------------------------------------------------------------------------
# EQ presets (no headset connection needed)
# ---------------------------------------------------------------------------


def list_eq_presets(model: ModelData | None = None) -> list[dict[str, object]]:
    """Return all EQ presets (built-in + custom). Uses default model if none given."""
    if model is None:
        model = default_model()
    eq_cfg = model.get("eq", {})
    presets = eq_cfg.get("presets", {})
    result: list[dict[str, object]] = []
    for key, p in presets.items():
        result.append({"name": p.get("label", key), "builtin": True, "arg": key})
    for custom in load_custom_presets():
        result.append(
            {"name": custom.get("name", ""), "builtin": False, "arg": custom.get("name", "")}
        )
    return result


def add_custom_preset(name: str, bands: list[int]) -> None:
    """Save a custom EQ preset. Max 3 custom presets. No headset connection needed."""
    presets = load_custom_presets()
    if len(presets) >= 3:
        raise ShokzError(
            f"Cannot add preset: maximum 3 custom presets allowed (have {len(presets)})"
        )
    _validate_bands(bands)
    presets.append({"name": name, "bands": bands})
    save_custom_presets(presets)


def update_custom_preset(original_name: str, new_name: str, bands: list[int]) -> None:
    """Replace a custom preset in-place (preserves list order)."""
    presets = load_custom_presets()
    for p in presets:
        if p.get("name") == original_name:
            _validate_bands(bands)
            p["name"] = new_name
            p["bands"] = bands
            save_custom_presets(presets)
            return
    raise ShokzError(f"Preset '{original_name}' not found.")


def delete_custom_preset(name: str) -> None:
    """Remove a custom EQ preset by name. No headset connection needed."""
    presets = load_custom_presets()
    filtered = [p for p in presets if p.get("name") != name]
    if len(filtered) == len(presets):
        raise ShokzError(f"Preset '{name}' not found.")
    save_custom_presets(filtered)


# ---------------------------------------------------------------------------
# Headset detection
# ---------------------------------------------------------------------------


def _scan_for_headset(oui_prefixes: list[str]) -> str | None:
    try:
        out = subprocess.run(
            ["bluetoothctl", "devices"], capture_output=True, text=True, timeout=5
        ).stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    for line in out.splitlines():
        parts = line.split()
        if len(parts) < 2:
            continue
        mac = parts[1].lower()
        for prefix in oui_prefixes:
            if mac.startswith(prefix.lower()):
                return parts[1]
    return None


def _sdp_channel(mac: str) -> int | None:
    try:
        out = subprocess.run(
            ["sdptool", "browse", "--l2cap", mac], capture_output=True, text=True, timeout=8
        ).stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    in_serial = False
    for line in out.splitlines():
        if "Serial Port" in line:
            in_serial = True
        if in_serial and "Channel:" in line:
            with contextlib.suppress(ValueError):
                return int(line.split("Channel:")[1].strip())
    return None


def _discover_mac(model: ModelData | None) -> str:
    oui: list[str] = list(model.get("oui_prefixes", [])) if model is not None else []
    if not oui:
        for m in list_models():
            oui.extend(m.get("oui_prefixes", []))
    mac = _scan_for_headset(oui) or ""
    if not mac:
        raise ShokzError("No Shokz headset found. Pair it first, or use --mac.")
    return mac


def _identify_model_from_headset(mac: str, channel: int) -> tuple[ModelData, int]:
    try:
        s = connect(mac, channel)
    except OSError as e:
        raise ShokzError(f"Cannot connect to {mac}: {e}") from e
    try:
        firmware = _handshake(s)
    finally:
        s.close()
    model = _find_model_by_prefix(firmware)
    if model is None:
        known = [m.get("firmware_prefix", "?") for m in list_models()]
        raise ShokzError(
            f"Unknown firmware prefix in '{firmware}'. "
            f"Known: {known}. Use --model or add a model YAML."
        )
    return model, model.get("bluetooth", {}).get("rfcomm_channel", channel)


def resolve_headset(
    mac: str | None = None, model_name: str | None = None
) -> tuple[str, ModelData, int]:
    """Detect the headset and return (mac, model, channel)."""
    model: ModelData | None = _load_model_by_name(model_name) if model_name is not None else None
    resolved_mac = mac if mac else _discover_mac(model)

    if model is not None:
        channel: int = model.get("bluetooth", {}).get("rfcomm_channel", DEFAULT_CHANNEL)
        return resolved_mac, model, channel

    mac_lower = resolved_mac.lower()
    model = next(
        (
            m
            for m in list_models()
            if any(mac_lower.startswith(p.lower()) for p in m.get("oui_prefixes", []))
        ),
        None,
    )
    if model is not None:
        channel = model.get("bluetooth", {}).get("rfcomm_channel", DEFAULT_CHANNEL)
        return resolved_mac, model, channel

    channel = _sdp_channel(resolved_mac) or DEFAULT_CHANNEL
    model, channel = _identify_model_from_headset(resolved_mac, channel)
    return resolved_mac, model, channel


# ---------------------------------------------------------------------------
# Low-level socket helpers
# ---------------------------------------------------------------------------


def _handshake(s: socket.socket) -> str:
    s.send(build_packet(CMD_FIRMWARE, b""))
    packets = drain(s, timeout=2.0)
    for cmd_id, payload in packets:
        if cmd_id == (RESPONSE_BIT | CMD_FIRMWARE) and payload:
            return payload[1:].split(b"\x00")[0].decode("ascii", "replace")
    return ""


def _send_cmd(s: socket.socket, cmd_id: int, payload: bytes) -> bytes:
    s.send(build_packet(cmd_id, payload))
    packets = drain(s, timeout=1.0)
    for _, resp_payload in packets:
        return resp_payload
    return b""


# ---------------------------------------------------------------------------
# Headset commands (all require connection)
# ---------------------------------------------------------------------------


def get_headset_info(mac: str, model: ModelData, channel: int) -> dict[str, object]:
    """Return headset info as a structured dict."""
    s = connect(mac, channel)
    try:
        firmware = _handshake(s)
        result: dict[str, object] = {
            "name": model.get("name", "?"),
            "firmware": firmware,
            "battery_pct": None,
            "battery_raw": None,
            "battery_scale": 9,
            "paired_devices": [],
        }

        batt_cfg = model.get("battery", {})
        batt_cmd = batt_cfg.get("command", -1)
        batt_scale = batt_cfg.get("scale", 9)
        if batt_cmd >= 0:
            s.send(build_packet(batt_cmd, b""))
            for cmd_id, payload in drain(s, 0.5):
                if cmd_id == (RESPONSE_BIT | batt_cmd) and payload:
                    level = payload[1]
                    pct = min(100, (level + 1) * (100 // (batt_scale + 1)))
                    result["battery_raw"] = level
                    result["battery_scale"] = batt_scale
                    result["battery_pct"] = pct

        di_cfg = model.get("device_info", {})
        di_cmd = di_cfg.get("command", -1)
        if di_cmd >= 0:
            s.send(build_packet(di_cmd, b""))
            devices: list[dict[str, object]] = []
            for cmd_id, payload in drain(s, 0.5):
                if cmd_id == (RESPONSE_BIT | di_cmd) and payload and len(payload) >= 4:
                    num = payload[1]
                    i = 3
                    for _ in range(num):
                        if i + 7 > len(payload):
                            break
                        dev_mac = ":".join(f"{b:02x}" for b in payload[i : i + 6])
                        active = payload[i + 6]
                        i += 7
                        name_len = payload[i]
                        i += 1
                        name = payload[i : i + name_len].decode("ascii", "replace").rstrip("\x00")
                        i += name_len + 1
                        devices.append({"mac": dev_mac, "name": name, "active": bool(active)})
            result["paired_devices"] = devices

        return result
    finally:
        s.close()


def _validate_bands(bands: list[int]) -> None:
    for b in bands:
        if b < -12 or b > 12:
            raise ShokzError(f"band value {b} out of range -12..12")


def _resolve_preset_name(name: str, model: ModelData) -> tuple[int, list[int]]:
    eq_cfg = model.get("eq", {})
    presets = eq_cfg.get("presets", {})
    if name in presets:
        p = presets[name]
        return p.get("id", 1), list(p.get("bands", []))
    for p in presets.values():
        if p.get("label", "") == name:
            return p.get("id", 1), list(p.get("bands", []))
    custom_preset_id: int = eq_cfg.get("custom_preset_id", 1)
    for custom in load_custom_presets():
        if custom.get("name") == name:
            bands_raw = custom.get("bands", [])
            return custom_preset_id, [_as_int(b) for b in cast(list[object], bands_raw)]
    raise ShokzError(f"Unknown preset '{name}'.")


def apply_eq_preset(
    mac: str,
    model: ModelData,
    channel: int,
    preset_name: str,
    custom_bands: list[int] | None = None,
) -> bool:
    """Apply an EQ preset. Returns True on success."""
    eq_cfg = model.get("eq", {})
    eq_cmd = eq_cfg.get("command", -1)
    if eq_cmd < 0:
        raise ShokzError("This model has no EQ command defined.")

    presets = eq_cfg.get("presets", {})

    if preset_name == "custom" and custom_bands is not None:
        first_preset = next(iter(presets.values()), EqPreset())
        preset_id: int = eq_cfg.get("custom_preset_id", first_preset.get("id", 1))
        bands = custom_bands[:7] + [0] * max(0, 7 - len(custom_bands))
        _validate_bands(bands)
        state_name = "custom"
    elif preset_name in presets:
        p = presets[preset_name]
        preset_id = p.get("id", 1)
        bands = list(p.get("bands", []))
        state_name = preset_name
    else:
        preset_id, bands = _resolve_preset_name(preset_name, model)
        _validate_bands(bands)
        state_name = preset_name

    byte_mask = 0xFF
    payload = bytes([preset_id & byte_mask] + [b & byte_mask for b in bands])
    s = connect(mac, channel)
    try:
        _handshake(s)
        resp = _send_cmd(s, eq_cmd, payload)
        ok = resp == b"\x00\x00\x00\x00"
        if ok:
            save_state(state_name)
        return ok
    finally:
        s.close()


def apply_lang_slots(mac: str, model: ModelData, channel: int, slots: list[str]) -> bool:
    """Set language priority slots. Returns True on success."""
    lang_cfg = model.get("language", {})
    lang_cmd = lang_cfg.get("command", -1)
    lang_codes = lang_cfg.get("codes", {})

    if lang_cmd < 0:
        raise ShokzError("This model has no language command defined.")

    codes: list[int] = []
    for lang in slots[:4]:
        if lang not in lang_codes:
            raise ShokzError(f"Unknown language '{lang}'. Use: {', '.join(lang_codes)}")
        codes.append(lang_codes[lang])

    s = connect(mac, channel)
    try:
        _handshake(s)
        for code in codes:
            payload = struct.pack("<I", code)
            _send_cmd(s, lang_cmd, payload)
        _send_cmd(s, lang_cmd, struct.pack("<I", 0))
        return True
    finally:
        s.close()
