#!/usr/bin/env python3 -I
"""shokz_config.py — configure Shokz headsets from the command line.

Headset model definitions live in models/*.yaml next to this script.
The headset MAC and model are auto-detected on first connect; use --mac / --model
to override.

Usage (interactive):
  python3 -I shokz_config.py [--mac MAC] [--model MODEL]

Usage (non-interactive):
  python3 -I shokz_config.py info
  python3 -I shokz_config.py eq standard
  python3 -I shokz_config.py eq vocal
  python3 -I shokz_config.py eq custom 0 0 3 2 2 0 0   # 7 signed-int bands
  python3 -I shokz_config.py lang en zh ko ja           # up to 4 slots
"""

import argparse
import contextlib
import json
import socket
import struct
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import TypedDict, cast

# `-I` (isolated mode) strips the script directory from sys.path; re-add it
# so `protocol.py` (a sibling of this file) can be imported as a plain module.
sys.path.insert(0, str(Path(__file__).parent))

import yaml

from protocol import (
    CMD_FIRMWARE,
    DEFAULT_CHANNEL,
    RESPONSE_BIT,
    build_packet,
    connect,
    drain,
)


class ShokzError(Exception):
    """Raised for user-facing configuration errors; caught in main() for clean exit."""


def _config_dir() -> Path:
    """Return ~/.config/openshokz, creating it if absent."""
    d = Path.home() / ".config" / "openshokz"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _load_presets() -> list[dict[str, object]]:
    """Read custom presets from presets.json; return [] if absent."""
    path = _config_dir() / "presets.json"
    if not path.exists():
        return []
    return list(json.loads(path.read_text()))


def _save_presets(presets: list[dict[str, object]]) -> None:
    """Atomically write custom presets to presets.json."""
    path = _config_dir() / "presets.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(presets, indent=2))
    tmp.rename(path)


def _load_state() -> dict[str, str]:
    """Read state.json; return {} if absent."""
    path = _config_dir() / "state.json"
    if not path.exists():
        return {}
    return dict(json.loads(path.read_text()))


def _save_state(active_eq: str) -> None:
    """Atomically write active EQ preset name to state.json."""
    path = _config_dir() / "state.json"
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"active_eq": active_eq, "updated": datetime.now().isoformat()}))
    tmp.rename(path)


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


def _models_dir() -> Path:
    return Path(__file__).parent / "models"


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


def _load_model(path: Path) -> ModelData:
    with open(path) as f:
        raw: object = yaml.safe_load(f)
    return _coerce_model(raw)


def _find_model_by_prefix(firmware: str) -> ModelData | None:
    for yaml_path in _models_dir().glob("*.yaml"):
        try:
            m = _load_model(yaml_path)
        except Exception:
            continue
        prefix = m.get("firmware_prefix", "")
        if prefix and firmware.startswith(prefix):
            return m
    return None


def _list_models() -> list[ModelData]:
    models: list[ModelData] = []
    for yaml_path in sorted(_models_dir().glob("*.yaml")):
        with contextlib.suppress(Exception):
            models.append(_load_model(yaml_path))
    return models


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
    """Query SDP for the Serial Port Profile channel on the given headset."""
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
            try:
                return int(line.split("Channel:")[1].strip())
            except ValueError:
                break
    return None


def _handshake(s: socket.socket) -> str:
    """Send firmware-version query, block 2 s for headset settle. Return firmware string."""
    _ = s.send(build_packet(CMD_FIRMWARE, b""))
    packets = drain(s, timeout=2.0)
    for cmd_id, payload in packets:
        if cmd_id == (RESPONSE_BIT | CMD_FIRMWARE) and payload:
            return payload[1:].split(b"\x00")[0].decode("ascii", "replace")
    return ""


def _send_cmd(s: socket.socket, cmd_id: int, payload: bytes) -> bytes:
    _ = s.send(build_packet(cmd_id, payload))
    packets = drain(s, timeout=1.0)
    for _, resp_payload in packets:
        return resp_payload
    return b""


def _load_model_arg(model_arg: str) -> ModelData:
    model_path = _models_dir() / model_arg
    if not model_path.exists():
        model_path = _models_dir() / f"{model_arg}.yaml"
    if not model_path.exists():
        raise ShokzError(f"Model file not found: {model_arg}")
    return _load_model(model_path)


def _discover_mac(model: ModelData | None) -> str:
    oui: list[str] = list(model.get("oui_prefixes", [])) if model is not None else []
    if not oui:
        for m in _list_models():
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
        known = [m.get("firmware_prefix", "?") for m in _list_models()]
        raise ShokzError(
            f"Unknown firmware prefix in '{firmware}'. "
            f"Known: {known}. Use --model or add a model YAML."
        )
    return model, model.get("bluetooth", {}).get("rfcomm_channel", channel)


def _resolve(mac_arg: str | None, model_arg: str | None) -> tuple[str, ModelData, int]:
    model: ModelData | None = _load_model_arg(model_arg) if model_arg is not None else None
    mac = mac_arg if mac_arg else _discover_mac(model)

    if model is not None:
        channel: int = model.get("bluetooth", {}).get("rfcomm_channel", DEFAULT_CHANNEL)
        return mac, model, channel

    # Match model by OUI prefix before running SDP — sdptool browse triggers a
    # full L2CAP connection that causes bluetoothd to grab the RFCOMM channel.
    mac_lower = mac.lower()
    model = next(
        (
            m
            for m in _list_models()
            if any(mac_lower.startswith(p.lower()) for p in m.get("oui_prefixes", []))
        ),
        None,
    )
    if model is not None:
        channel = model.get("bluetooth", {}).get("rfcomm_channel", DEFAULT_CHANNEL)
        return mac, model, channel

    channel = _sdp_channel(mac) or DEFAULT_CHANNEL
    model, channel = _identify_model_from_headset(mac, channel)
    return mac, model, channel


def cmd_info(mac: str, model: ModelData, channel: int) -> None:
    s = connect(mac, channel)
    try:
        firmware = _handshake(s)
        print(f"Model    : {model.get('name', '?')}")
        print(f"Firmware : {firmware}")

        batt_cfg = model.get("battery", {})
        batt_cmd = batt_cfg.get("command", -1)
        batt_scale = batt_cfg.get("scale", 9)
        if batt_cmd >= 0:
            _ = s.send(build_packet(batt_cmd, b""))
            for cmd_id, payload in drain(s, 0.5):
                if cmd_id == (RESPONSE_BIT | batt_cmd) and payload:
                    level = payload[1]
                    pct = min(100, (level + 1) * (100 // (batt_scale + 1)))
                    print(f"Battery  : {level}/{batt_scale} ({pct}%)")

        di_cfg = model.get("device_info", {})
        di_cmd = di_cfg.get("command", -1)
        if di_cmd >= 0:
            _ = s.send(build_packet(di_cmd, b""))
            for cmd_id, payload in drain(s, 0.5):
                if cmd_id == (RESPONSE_BIT | di_cmd) and payload and len(payload) >= 4:
                    print("Paired devices:")
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
                        status = "connected" if active else "paired"
                        print(f"  [{status}] {name} ({dev_mac})")
    finally:
        s.close()


def _validate_bands(bands: list[int]) -> None:
    """Raise ShokzError if any band value is outside -12..12."""
    for b in bands:
        if b < -12 or b > 12:
            raise ShokzError(f"band value {b} out of range -12..12")


def _resolve_preset_name(name: str, model: ModelData) -> tuple[int, list[int]]:
    """Resolve a preset name to (preset_id, bands).

    Built-in presets (matched by key or label) take precedence over custom.
    Raises ShokzError if the name is not found.
    """
    eq_cfg = model.get("eq", {})
    presets = eq_cfg.get("presets", {})
    # Check built-in by key
    if name in presets:
        p = presets[name]
        return p.get("id", 1), list(p.get("bands", []))
    # Check built-in by label
    for p in presets.values():
        if p.get("label", "") == name:
            return p.get("id", 1), list(p.get("bands", []))
    # Check custom presets
    custom_preset_id: int = eq_cfg.get("custom_preset_id", 1)
    for custom in _load_presets():
        if custom.get("name") == name:
            bands_raw = custom.get("bands", [])
            return custom_preset_id, [_as_int(b) for b in cast(list[object], bands_raw)]
    raise ShokzError(f"Unknown preset '{name}'. Run 'eq list --json' to see available presets.")


def cmd_eq_list(model: ModelData) -> None:
    """Print all EQ presets (built-in + custom) as JSON. No headset connection needed."""
    eq_cfg = model.get("eq", {})
    presets = eq_cfg.get("presets", {})
    result: list[dict[str, object]] = []
    for key, p in presets.items():
        result.append({"name": p.get("label", key), "builtin": True, "arg": key})
    for custom in _load_presets():
        result.append(
            {"name": custom.get("name", ""), "builtin": False, "arg": custom.get("name", "")}
        )
    print(json.dumps(result, indent=2))


def cmd_eq(
    mac: str,
    model: ModelData,
    channel: int,
    preset_name: str,
    custom_bands: list[int] | None = None,
) -> None:
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
        label = "custom"
        state_name = "custom"
    elif preset_name in presets:
        p = presets[preset_name]
        preset_id = p.get("id", 1)
        bands = list(p.get("bands", []))
        label = p.get("label", preset_name)
        state_name = preset_name
    else:
        # Try named custom preset lookup (named presets not in built-in list)
        preset_id, bands = _resolve_preset_name(preset_name, model)
        _validate_bands(bands)
        label = preset_name
        state_name = preset_name

    byte_mask = 0xFF
    payload = bytes([preset_id & byte_mask] + [b & byte_mask for b in bands])
    s = connect(mac, channel)
    try:
        _ = _handshake(s)
        resp = _send_cmd(s, eq_cmd, payload)
        if resp == b"\x00\x00\x00\x00":
            band_str = ", ".join(f"{b:+d}" if b else "0" for b in bands)
            print(f"EQ set: {label} (preset_id={preset_id:#x}, bands=[{band_str}])")
            _save_state(state_name)
        else:
            print(f"Unexpected response: {resp.hex()}")
    finally:
        s.close()


def cmd_lang(mac: str, model: ModelData, channel: int, slots: list[str]) -> None:
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

    lang_by_code: dict[int, str] = {v: k for k, v in lang_codes.items()}

    s = connect(mac, channel)
    try:
        _ = _handshake(s)
        for code in codes:
            payload = struct.pack("<I", code)
            resp = _send_cmd(s, lang_cmd, payload)
            lang_key = lang_by_code.get(code, str(code))
            ok = resp == b"\x00\x00\x00\x00" or (len(resp) >= 2 and resp[1] == code)
            print(f"  Language slot: {lang_key} ({'OK' if ok else resp.hex()})")
        _ = _send_cmd(s, lang_cmd, struct.pack("<I", 0))
        print("Language slots committed.")
    finally:
        s.close()


def interactive(mac: str, model: ModelData, channel: int) -> None:
    eq_cfg = model.get("eq", {})
    presets = eq_cfg.get("presets", {})
    lang_cfg = model.get("language", {})
    lang_codes = lang_cfg.get("codes", {})

    menu_items: list[tuple[str, str]] = [("info", "Device info")]
    for key, p in presets.items():
        menu_items.append((f"eq:{key}", f"EQ: {p.get('label', key)}"))
    if presets:
        menu_items.append(("eq:custom", "EQ: Custom bands"))
    if lang_codes:
        menu_items.append(("lang", "Language slots"))

    while True:
        print(f"\n{model.get('name', 'Shokz')} — Configuration")
        for i, (_, item_label) in enumerate(menu_items, 1):
            print(f"  {i}) {item_label}")
        print("  q) Quit")
        choice = input("Choice: ").strip().lower()
        if choice == "q":
            break
        try:
            idx = int(choice) - 1
            action = menu_items[idx][0]
        except (ValueError, IndexError):
            print("Unknown choice.")
            continue

        if action == "info":
            cmd_info(mac, model, channel)
        elif action.startswith("eq:"):
            preset = action[3:]
            if preset == "custom":
                print("Enter 7 EQ band values (signed dB, space-separated):")
                freqs = eq_cfg.get("band_frequencies", [])
                if freqs:
                    print(f"  Bands: {' '.join(str(f) + 'Hz' for f in freqs)}")
                raw_input = input("  Values: ").strip().split()
                try:
                    bands = [int(x) for x in raw_input[:7]]
                except ValueError:
                    print("Invalid — use integers like: -4 0 3 2 2 0 0")
                    continue
                cmd_eq(mac, model, channel, "custom", bands)
            else:
                cmd_eq(mac, model, channel, preset)
        elif action == "lang":
            print(f"Enter up to 4 language codes ({', '.join(lang_codes)}), space-separated:")
            raw_input = input("  Languages: ").strip().lower().split()
            if raw_input:
                cmd_lang(mac, model, channel, raw_input)


def main() -> None:
    parser = argparse.ArgumentParser(description="Configure Shokz headsets from the command line.")
    _ = parser.add_argument("--mac", help="Headset Bluetooth MAC address")
    _ = parser.add_argument("--model", help="Model YAML filename in models/")
    _ = parser.add_argument(
        "command",
        nargs="?",
        choices=["info", "eq", "lang"],
        help="Command to run (omit for interactive menu)",
    )
    _ = parser.add_argument("args", nargs="*", help="Command arguments")
    namespace = parser.parse_args()

    mac_arg: str | None = getattr(namespace, "mac", None)
    model_arg: str | None = getattr(namespace, "model", None)
    command: str | None = getattr(namespace, "command", None)
    args: list[str] = getattr(namespace, "args", []) or []

    try:
        # eq list --json doesn't need a headset connection; handle before _resolve
        if command == "eq" and args and args[0] == "list":
            _, model, _ = _resolve(mac_arg, model_arg)
            cmd_eq_list(model)
            return

        mac, model, channel = _resolve(mac_arg, model_arg)

        match command:
            case None:
                interactive(mac, model, channel)
            case "info":
                cmd_info(mac, model, channel)
            case "eq":
                if not args:
                    parser.error("eq requires a preset name: standard|vocal|custom [bands...]")
                preset = args[0].lower()
                if preset == "custom":
                    try:
                        custom_bands = [int(x) for x in args[1:8]]
                    except ValueError:
                        parser.error("Custom EQ needs integer band values")
                    cmd_eq(mac, model, channel, "custom", custom_bands)
                else:
                    cmd_eq(mac, model, channel, preset)
            case "lang":
                if not args:
                    parser.error("lang requires at least one language code")
                cmd_lang(mac, model, channel, [a.lower() for a in args[:4]])
    except ShokzError as exc:
        sys.exit(str(exc))


if __name__ == "__main__":
    main()
