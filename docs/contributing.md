# Adding Support for a New Shokz Model

Each supported headset is described by a YAML file in `models/`.
The Python code contains no model-specific data — everything lives in the YAML.

## Prerequisites

- A Linux machine with BlueZ (`bluetoothctl`, `sdptool`)
- The headset paired and connected
- An Android phone with the official Shokz app
- Python 3.11+ with PyYAML (`pip install pyyaml`)
- Optional: Wireshark / tshark for deeper analysis

## Step 1 — Run the probe script

```bash
python3 -I scripts/probe_model.py
# or, if your headset isn't auto-detected:
python3 -I scripts/probe_model.py --mac AA:BB:CC:DD:EE:FF
```

This connects to your headset, queries every command ID 0x00–0x1F, and writes
`models/<FIRMWARE_PREFIX>.yaml.template`. Commands that respond are printed with
their payloads.

## Step 2 — Capture Bluetooth traffic

You need captures for each configurable feature (EQ, language, etc.).

### 2a. Enable HCI snoop logging

On your Android phone: **Settings → Developer Options → Bluetooth HCI snoop log → ON**.
Toggle Bluetooth off then on.

### 2b. Use the Shokz app

Connect your headset, then in the app change one setting at a time:

- Switch EQ preset (note which one)
- Change language slots
- Toggle multipoint, etc.

### 2c. Capture the log

```bash
adb bugreport /tmp/capture.zip
unzip -j /tmp/capture.zip "FS/data/log/bt/btsnoop_hci.log" -d /tmp/
```

Or using 7z if unzip fails:
```bash
7z e /tmp/capture.zip "FS/data/log/bt/btsnoop_hci.log" -o/tmp/
```

### 2d. Extract DLCI 0x1d frames

Replace `AA:BB:CC:DD:EE:FF` with your headset's MAC:

```bash
tshark -r /tmp/btsnoop_hci.log \
  -Y "btrfcomm.dlci == 0x1d && (bthci_acl.src.bd_addr == AA:BB:CC:DD:EE:FF || \
      bthci_acl.dst.bd_addr == AA:BB:CC:DD:EE:FF)" \
  -T fields -e frame.number -e frame.time_relative \
  -e bthci_acl.src.bd_addr -e bthci_acl.dst.bd_addr -e data.data \
  > /tmp/capture_dlci1d.txt
```

### 2e. Decode the frames

```bash
python3 -I scripts/decode_shokz.py /tmp/capture_dlci1d.txt
```

This prints all commands and payloads. Find the write commands that change when you
switch EQ or language — those are the commands to document.

## Step 3 — Fill in the template

Open `models/<PREFIX>.yaml.template` and fill in each `TODO:` field:

| Field | How to find it |
|-------|---------------|
| `name` | Product name from the box |
| `eq.command` | The command ID that changes when you switch EQ in the app |
| `eq.presets` | One entry per preset: the command payload when you select it |
| `language.command` | Command ID that changes when you switch language |
| `language.codes` | Payload value for each language (typically 0x00–0x03) |
| `device_info.command` | Command that returns a list of paired devices |

### Identifying EQ preset payloads

The EQ payload is 8 bytes: `[preset_id, band0, band1, band2, band3, band4, band5, band6]`.
Band values are **signed int8** (e.g., `0xfc` = −4 dB).

When you switch from "Standard" to another preset in the app, the decode output shows
something like:

```
>> [cmd=0x0e] payload=02fc000302020000
```

That means preset_id=2, bands=[−4, 0, +3, +2, +2, 0, 0].

### field_0x0A (packet checksum)

Every packet has a 2-byte checksum at offset 0x0A:

```
field_0x0A = CRC16/Maxim(packet[0x0C:])
```

CRC16/Maxim: poly=0x8005, init=0x0000, refin=True, refout=True, xorout=0xFFFF.
The `_crc16_maxim()` function in `shokz_config.py` and `probe_model.py` computes this.
**You do not need to figure this out yourself** — the code handles it automatically.

## Step 4 — Test your model file

Rename and activate:

```bash
cp models/<PREFIX>.yaml.template models/<PREFIX>.yaml
python3 -I shokz_config.py --model <PREFIX>.yaml info
python3 -I shokz_config.py --model <PREFIX>.yaml eq standard
```

## Step 5 — Submit a PR

Include:
- `models/<YOUR_MODEL>.yaml` — the new model file
- `data/cap*/btsnoop_hci.log` or `data/cap*/shokz_dlci1d.txt` — the capture(s) you
  used to identify the commands (helps reviewers verify your data)
- A brief description of what you tested and what still needs validation

## Protocol overview

See `docs/protocol.md` for the full packet format and command reference.
The key points for a new model:

- Transport: Classic Bluetooth, RFCOMM (SPP), DLCI 0x1d = server channel 14 (verify with probe script)
- Every packet starts with `a5 5a` and has a CRC16/Maxim checksum at offset 0x0A
- Reads use `proto=2` (tag-2 value); writes use `proto=1`
- The headset needs ~2 seconds after the firmware-version query before it accepts writes
- Voice announcements are in headset firmware — the app sends a command, the headset speaks

## Notes on protocol differences between models

Different Shokz models (OpenRun, OpenFit, OpenComm, etc.) share the same packet
framing and CRC but may use different command IDs, different payload layouts, and
different RFCOMM channel numbers. The `firmware_prefix` field in the YAML is matched
against the firmware version string reported by `cmd_0x02` to auto-select the right
model file.
