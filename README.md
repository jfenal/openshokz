# openshokz

Open-source command-line configurator for Shokz Bluetooth headsets.

Reverse-engineered from Bluetooth HCI captures of the official Android app.
Communicates directly over RFCOMM without requiring the Shokz app or a cloud account.

## Supported devices

| Model | Firmware prefix | Status |
|-------|----------------|--------|
| OpenComm2 2025 (USB-C) | `HC_HU` | ✅ Full support |

Adding new models is straightforward — see [docs/contributing.md](docs/contributing.md).

## Features

- **Device info** — firmware version, battery level, paired device list
- **EQ presets** — switch between Standard and Vocal Booster; send custom band values
- **Language slots** — set voice prompt language priority (English, Chinese, Japanese, Korean)
- **Auto-detection** — finds the headset by Bluetooth OUI; no MAC address needed
- **Data-driven** — all device constants live in `models/*.yaml`, not in code

## Requirements

- Linux with BlueZ (`bluetoothctl`, `python3`)
- Headset paired to your computer
- Python 3.11+
- `pip install PyYAML`

## Usage

```bash
# Device info (firmware, battery, paired devices)
python3 -I shokz_config.py info

# EQ presets
python3 -I shokz_config.py eq standard
python3 -I shokz_config.py eq vocal

# Custom EQ — 7 signed-dB band values (~250 500 1k 2k 4k 6k 8k Hz)
python3 -I shokz_config.py eq custom 0 0 4 3 2 0 0

# Language slots (up to 4, in priority order)
python3 -I shokz_config.py lang zh en ko ja

# Interactive menu
python3 -I shokz_config.py
```

Override auto-detection:

```bash
python3 -I shokz_config.py --mac A0:0C:E2:8C:BB:59 info
python3 -I shokz_config.py --model opencomm2_2025.yaml info
```

## Troubleshooting

**"Device or resource busy"** — BlueZ auto-connected the SPP profile and is holding
channel 14. The script detects this and skips `sdptool` for known models (OUI match),
but if it still fails, restart Bluetooth: `sudo systemctl restart bluetooth` and try
again before BlueZ reconnects.

**"Cannot connect: timed out"** — Headset is off or out of range. Wake it (tap the
button) and ensure the phone or another device is connected so it stays awake.

## How it works

The headset exposes a proprietary SPP (Serial Port Profile) channel alongside standard
HFP. All configuration commands are sent as TLV-framed packets over RFCOMM channel 14
(DLCI `0x1d`), authenticated with a per-packet CRC16/Maxim checksum.

See [docs/protocol.md](docs/protocol.md) for the full protocol reference.

## Adding a new model

Run the probe script against an unknown headset:

```bash
python3 -I scripts/probe_model.py
```

This generates a `models/<prefix>.yaml.template` with the commands the headset responds
to. Fill in the preset names, language codes, and labels, then open a PR.

See [docs/contributing.md](docs/contributing.md) for the full workflow including how to
capture Bluetooth traffic.

## Project structure

```
shokz_config.py       CLI entry point (auto-detects headset and model)
protocol.py           Shared BT protocol: CRC16, packet builder/parser, named constants
models/               YAML model definitions (one file per headset family)
scripts/
  probe_model.py      Discover commands on an unknown headset → YAML template
  send_cmd.py         Low-level send tool for testing
  decode_shokz.py     Decode captured tshark DLCI 0x1d frame dumps
tests/
  test_protocol.py    55 unit tests (CRC, packet builder, parser, model loader)
docs/
  protocol.md         Full protocol reference
  contributing.md     How to add new headset models
  capture_setup.md    How to capture Bluetooth traffic for reverse engineering
  TODO.md             Known unknowns and future work
```

## Development

```bash
pip install PyYAML mypy basedpyright ruff pre-commit
pre-commit install

# Run checks
ruff check shokz_config.py protocol.py scripts/
python3 -m mypy shokz_config.py protocol.py scripts/
python3 -m basedpyright shokz_config.py protocol.py scripts/
python3 -m pytest tests/
gourmand check
```

## License

GPL-3.0 — contributions welcome.
