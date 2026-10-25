#!/usr/bin/env python3 -I
"""probe_model.py — discover Shokz protocol commands on an unknown headset.

Connects to the headset, queries every command ID 0x00-0x1F, records which
ones respond, and writes a YAML template to models/<firmware_prefix>.yaml.template.

Usage:
  python3 -I scripts/probe_model.py [--mac MAC] [--channel CHANNEL]
"""

import argparse
import subprocess
import sys
from pathlib import Path

from openshokz.protocol import (
    CMD_FIRMWARE,
    DEFAULT_CHANNEL,
    RESPONSE_BIT,
    build_packet,
    connect,
    drain,
)

PROBE_RANGE = range(0x00, 0x20)
KNOWN_OUI_PREFIXES = ["a0:0c:e2", "00:07:80"]  # Shokz / AfterShokz


class ProbeError(Exception):
    """User-facing error during headset probing."""


def _firmware_from_packets(pkts: list[tuple[int, bytes]]) -> str:
    for cmd_id, payload in pkts:
        if cmd_id == (RESPONSE_BIT | CMD_FIRMWARE) and payload:
            return payload[1:].split(b"\x00")[0].decode("ascii", "replace")
    return ""


def _scan_for_headset() -> str | None:
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
        for prefix in KNOWN_OUI_PREFIXES:
            if mac.startswith(prefix.lower()):
                return parts[1]
    return None


def _get_rfcomm_channel(mac: str) -> int:
    try:
        out = subprocess.run(
            ["sdptool", "browse", "--l2cap", mac], capture_output=True, text=True, timeout=8
        ).stdout
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return DEFAULT_CHANNEL
    in_serial = False
    for line in out.splitlines():
        if "Serial Port" in line:
            in_serial = True
        if in_serial and "Channel:" in line:
            try:
                return int(line.split("Channel:")[1].strip())
            except ValueError:
                break
    return DEFAULT_CHANNEL


def probe(mac: str, channel: int) -> None:
    print(f"Connecting to {mac} channel {channel}...")
    try:
        s = connect(mac, channel)
    except OSError as e:
        raise ProbeError(f"Connection failed: {e}") from e

    _ = s.send(build_packet(CMD_FIRMWARE, b""))
    firmware = _firmware_from_packets(drain(s, timeout=2.0))
    print(f"Firmware : {firmware}")

    responses: dict[int, bytes] = {}
    print(f"Probing commands 0x00-0x{PROBE_RANGE.stop - 1:02x}...")
    for cid in PROBE_RANGE:
        try:
            _ = s.send(build_packet(cid, b""))
            pkts = drain(s, timeout=0.4)
            for rcid, rp in pkts:
                if rcid == (RESPONSE_BIT | cid) or rcid >= 0:
                    responses[cid] = rp
                    print(f"  0x{cid:02x} -> 0x{rcid:04x}  {rp.hex() or '(empty)'}")
                    break
        except OSError:
            print(f"  0x{cid:02x} -> connection reset (reconnecting...)")
            s.close()
            try:
                s = connect(mac, channel)
                _ = s.send(build_packet(CMD_FIRMWARE, b""))
                drain(s, timeout=2.0)
            except OSError as e:
                raise ProbeError(f"Reconnect failed: {e}") from e

    s.close()

    firmware_prefix = firmware.split("_V_")[0] if "_V_" in firmware else firmware[:6]
    _write_template(mac, channel, firmware, firmware_prefix, responses)


def _write_template(
    mac: str,
    channel: int,
    firmware: str,
    prefix: str,
    responses: dict[int, bytes],
) -> None:
    models_dir = Path(__file__).parent.parent / "models"
    models_dir.mkdir(exist_ok=True)
    out_path = models_dir / f"{prefix}.yaml.template"

    responded_hex = ", ".join(f"0x{c:02x}" for c in sorted(responses))

    lines: list[str] = [
        "# Auto-generated template by probe_model.py",
        f"# Firmware: {firmware}",
        f"# MAC: {mac}",
        f"# Responded commands: {responded_hex}",
        f"# Edit this file, rename to {prefix}.yaml, and place in models/",
        "",
        'name: "TODO: e.g. OpenRun Pro 2"',
        f'firmware_prefix: "{prefix}"',
        "",
        "oui_prefixes:",
        f'  - "{mac[:8].lower()}"   # OUI from discovered MAC',
        "",
        "bluetooth:",
        f"  rfcomm_channel: {channel}",
        "",
    ]

    max_battery_level = 15
    for cid, payload in responses.items():
        if len(payload) >= 4 and payload[0] == 0 and 0 < payload[1] <= max_battery_level:
            lines += [
                "battery:",
                f"  command: {cid:#x}",
                f"  # Observed response: {payload.hex()}",
                "  scale: 9  # confirm: level N means N/scale * 100%",
                "",
            ]
            break

    lines += [
        "eq:",
        "  command: 0x??  # find the EQ command by changing EQ in the app and capturing",
        "  preset_id_byte: 0",
        "  band_bytes: [1, 2, 3, 4, 5, 6, 7]",
        "  band_frequencies: [250, 500, 1000, 2000, 4000, 6000, 8000]  # unconfirmed",
        "  presets:",
        "    standard:",
        "      id: 0x01",
        "      bands: [0, 0, 0, 0, 0, 0, 0]",
        "      label: Standard",
        "    # Add more presets after capturing with scripts/decode_shokz.py",
        "  custom_preset_id: 0x01",
        "",
        "language:",
        "  command: 0x??  # find language command from captures",
        "  codes:",
        "    en: 0x00",
        "    # Add other language codes as discovered",
        "",
        "device_info:",
        "  command: 0x??  # identify from captures",
        "",
        "# Raw probe results for reference:",
        "# command: response_hex",
    ]
    for cid, payload in sorted(responses.items()):
        lines.append(f"#   {cid:#04x}: {payload.hex() or '(empty)'}")

    out_path.write_text("\n".join(lines) + "\n")
    print(f"\nTemplate written to: {out_path}")
    print("Next steps:")
    print("  1. Capture BT traffic while using the headset app (see docs/contributing.md)")
    print("  2. Run: python3 -I scripts/decode_shokz.py data/<capture>.txt")
    print("  3. Fill in the fields marked with ??")
    print(f"  4. Rename {out_path.name} -> {prefix}.yaml")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Probe a Shokz headset to generate a model template."
    )
    _ = parser.add_argument("--mac", help="Headset Bluetooth MAC address")
    _ = parser.add_argument("--channel", type=int, help="RFCOMM channel (default: auto-detect)")
    opts = parser.parse_args()

    mac: str | None = getattr(opts, "mac", None)
    channel_arg: int | None = getattr(opts, "channel", None)

    if not mac:
        mac = _scan_for_headset()
        if not mac:
            sys.exit("No headset found. Pair it first or use --mac.")
        print(f"Auto-detected headset: {mac}")

    channel: int = channel_arg if channel_arg is not None else _get_rfcomm_channel(mac)
    try:
        probe(mac, channel)
    except ProbeError as exc:
        sys.exit(str(exc))


if __name__ == "__main__":
    main()
