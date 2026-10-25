"""openshokz CLI — thin wrapper around openshokz.core that prints results."""

from __future__ import annotations

import argparse
import json
import sys

from openshokz.core import (
    ShokzError,
    add_custom_preset,
    apply_eq_preset,
    apply_lang_slots,
    delete_custom_preset,
    get_headset_info,
    list_eq_presets,
    resolve_headset,
)


def _cmd_info(mac: str, model: object, channel: int, short: bool = False) -> None:
    assert isinstance(model, dict)
    info = get_headset_info(mac, model, channel)  # type: ignore[arg-type]
    print(f"Model    : {info.get('name', '?')}")
    print(f"Firmware : {info.get('firmware', '?')}")
    pct = info.get("battery_pct")
    raw = info.get("battery_raw")
    scale = info.get("battery_scale", 9)
    if pct is not None:
        print(f"Battery  : {raw}/{scale} ({pct}%)")
    if short:
        return
    devices = info.get("paired_devices", [])
    if devices:
        print("Paired devices:")
        for dev in devices:  # type: ignore[union-attr]
            assert isinstance(dev, dict)
            status = "connected" if dev.get("active") else "paired"
            print(f"  [{status}] {dev.get('name', '?')} ({dev.get('mac', '?')})")


def _interactive(mac: str, model: object, channel: int) -> None:
    assert isinstance(model, dict)
    m = model  # type: ignore[assignment]
    eq_cfg = m.get("eq", {})
    presets = eq_cfg.get("presets", {})
    lang_cfg = m.get("language", {})
    lang_codes = lang_cfg.get("codes", {})

    menu_items: list[tuple[str, str]] = [("info", "Device info")]
    for key, p in presets.items():
        menu_items.append((f"eq:{key}", f"EQ: {p.get('label', key)}"))
    if presets:
        menu_items.append(("eq:custom", "EQ: Custom bands"))
    if lang_codes:
        menu_items.append(("lang", "Language slots"))

    while True:
        print(f"\n{m.get('name', 'Shokz')} — Configuration")
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
            _cmd_info(mac, m, channel)
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
                apply_eq_preset(mac, m, channel, "custom", bands)  # type: ignore[arg-type]
            else:
                apply_eq_preset(mac, m, channel, preset)  # type: ignore[arg-type]
        elif action == "lang":
            print(f"Enter up to 4 language codes ({', '.join(lang_codes)}), space-separated:")
            raw_input = input("  Languages: ").strip().lower().split()
            if raw_input:
                apply_lang_slots(mac, m, channel, raw_input)  # type: ignore[arg-type]


def _handle_eq_noconnect(
    parser: argparse.ArgumentParser,
    mac_arg: str | None,
    model_arg: str | None,
    args: list[str],
) -> bool:
    """Handle eq subcommands that don't need a headset. Return True if handled."""
    if args and args[0] == "list":
        _, model, _ = resolve_headset(mac_arg, model_arg)
        presets = list_eq_presets(model)
        print(json.dumps(presets, indent=2))
        return True
    if len(args) >= 2 and args[0] == "preset":
        sub = args[1]
        if sub == "add" and len(args) >= 4:
            try:
                bands = [int(x) for x in args[3:10]]
            except ValueError:
                parser.error("eq preset add needs integer band values")
            add_custom_preset(args[2], bands)
            print(f"Preset '{args[2]}' saved.")
            return True
        if sub == "delete" and len(args) >= 3:
            delete_custom_preset(args[2])
            print(f"Preset '{args[2]}' deleted.")
            return True
        parser.error("Usage: eq preset add <name> b0..b6 | eq preset delete <name>")
    return False


def _handle_eq(
    parser: argparse.ArgumentParser,
    mac: str,
    model: object,
    channel: int,
    args: list[str],
) -> None:
    if not args:
        parser.error("eq requires a preset name: standard|vocal|custom [bands...]")
    preset = args[0].lower()
    if preset == "custom":
        try:
            custom_bands = [int(x) for x in args[1:8]]
        except ValueError:
            parser.error("Custom EQ needs integer band values")
        ok = apply_eq_preset(mac, model, channel, "custom", custom_bands)  # type: ignore[arg-type]
    else:
        ok = apply_eq_preset(mac, model, channel, args[0])  # type: ignore[arg-type]
    if not ok:
        sys.exit("Unexpected response from headset")


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
    _ = parser.add_argument(
        "--short", action="store_true", help="info: print only Model and Battery"
    )
    namespace = parser.parse_args()

    mac_arg: str | None = getattr(namespace, "mac", None)
    model_arg: str | None = getattr(namespace, "model", None)
    command: str | None = getattr(namespace, "command", None)
    args: list[str] = getattr(namespace, "args", []) or []
    short_flag: bool = getattr(namespace, "short", False)

    try:
        if command == "eq" and _handle_eq_noconnect(parser, mac_arg, model_arg, args):
            return

        mac, model, channel = resolve_headset(mac_arg, model_arg)

        match command:
            case None:
                _interactive(mac, model, channel)
            case "info":
                _cmd_info(mac, model, channel, short=short_flag)
            case "eq":
                _handle_eq(parser, mac, model, channel, args)
            case "lang":
                if not args:
                    parser.error("lang requires at least one language code")
                apply_lang_slots(mac, model, channel, [a.lower() for a in args[:4]])  # type: ignore[arg-type]
    except ShokzError as exc:
        sys.exit(str(exc))


if __name__ == "__main__":
    main()
