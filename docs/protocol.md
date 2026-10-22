# Shokz OpenComm2 2025 (USB-C) — Bluetooth Protocol

Reverse-engineered by observing HCI snoop logs from the official Android app.

## Device Information

- **Model**: Shokz OpenComm2 2025 (USB-C connector)
- **Headset MAC**: `a0:0c:e2:8c:bb:59`
- **Firmware**: `HC_HU_V_01_20251116`
- **Captures**: `data/btsnoop_hci.log`, `data/btsnoop_hci_lang.log`

## Transport

The headset uses **Classic Bluetooth** (not BLE) with two RFCOMM channels:

| DLCI | Profile | Purpose |
|------|---------|---------|
| `0x08` | HFP (Hands-Free Profile) | Phone call control, battery via `AT+IPHONEACCEV` |
| `0x1d` | Vendor SPP | All configuration commands |

Voice prompt audio (EQ mode announcements, language prompts) is **stored in headset firmware** — no audio is transmitted from the phone app. The app sends a command; the headset plays the announcement itself.

## Packet Framing (DLCI 0x1d)

Every packet starts with a 2-byte magic `a5 5a`, followed by a length field and direction flag, then a body of TLV entries.

```
Offset  Size  Field
0x00    2     Magic: a5 5a
0x02    2     Payload length (LE) = total size - 8
0x04    2     Direction: 00 00 = query, 01 00 = response
0x06    2     Padding: 00 00
0x08    2     Message length (LE)
0x0A    6     Correlation ID (varies per exchange)
0x10    4     Body container length (LE)
0x14    N     TLV body
```

Each TLV entry:

```
4 bytes  Tag (LE uint32)
4 bytes  Length (LE uint32)
N bytes  Value
```

Relevant tags:

| Tag | Role |
|-----|------|
| `0x02` | Protocol version — always `2` |
| `0x03` | Command ID (high bit `0x80000000` set in responses) |
| `0x04` | Payload data |

## Command Reference

### `0x02` — Firmware Version / Language Set

**Read** (empty payload):

```
<< 00 48 43 5f 48 55 5f 56 5f 30 31 5f 32 30 32 35 31 31 31 36 00...
   = "\x00HC_HU_V_01_20251116\0..."
```

**Write** (set language slot):

```
>> XX 00 00 00   (XX = language code)
<< 00 XX 00 00   (echo confirmation)
```

Language codes:

| Code | Language |
|------|---------|
| `0x00` | English |
| `0x01` | Chinese (Mandarin) |
| `0x02` | Japanese |
| `0x03` | Korean |

To configure language priority slots, send one write per slot in priority order. A trailing `00 00 00 00` write appears to commit the sequence.

Example — Chinese (1), English (2), Korean (3), Japanese (4):

```
>> 01 00 00 00   → << 00 01 00 00
>> 00 00 00 00   → << 00 00 00 00
>> 03 00 00 00   → << 00 03 00 00
>> 02 00 00 00   → << 00 02 00 00
>> 00 00 00 00   → << 00 00 00 00   (commit)
```

### `0x03` — Battery Level

Read-only. Response format: `00 NN FF 00`

- `NN`: level on 0–9 scale (9 = 100%, matches `AT+IPHONEACCEV` HFP value)
- `FF`: second byte — purpose unknown; observed as `0xff` at 100% charge

Also reported via HFP: `AT+IPHONEACCEV=2,1,<level>,2,0`

### `0x04` — Paired Device List

Read-only. Returns up to 3 paired devices.

Response layout:

```
00 03 00         header (3 devices)
<6 bytes MAC>    device MAC
<1 byte active>  0x00 = inactive, 0x01 = currently connected
1f               name length (31)
<31 bytes name>  device name, null-padded
... repeated per device
```

### `0x06` — Connection Status

Read-only. Always returns `00 00 00 00`. Queried after connection handshake.

### `0x08` — Link State

Read-only. Returns `00 01 00 00 00 00 00 00` when connected.

### `0x0b` — Multipoint: Activate Second Device

Write a 6-byte MAC address to connect that device as the second multipoint endpoint.

```
>> <6 bytes MAC>
<< 00 03 00 00   (acknowledgement; byte 1 = total paired count)
```

Side effect: headset initiates a Bluetooth connection to the target MAC. The `active` flag for that device in `cmd_0x04` changes from `0x00` to `0x01`.

**Deactivation**: removing a device from multipoint causes a headset disconnect/reconnect cycle. The headset remembers multipoint state across reconnects. Deactivation appears to be triggered at the ACL level (connection drop) rather than via a RFCOMM command.

### `0x0e` — EQ Preset

Writable. Sets the active EQ mode.

```
>> PP B0 B1 B2 B3 B4 B5 B6
```

- `PP`: preset ID
- `B0`–`B6`: EQ band adjustments (signed int8, dB relative to flat)

The OpenComm2 2025 has two presets:

| ID | Name | Bands (B0–B6) |
|----|------|---------------|
| `0x01` | Standard | 0, 0, 0, 0, 0, 0, 0 |
| `0x02` | Vocal Booster | −4, 0, +3, +2, +2, 0, 0 |

Response: `00 00 00 00` (acknowledgement).

**EQ band frequency mapping** (inferred from Vocal Booster shape — unconfirmed without a third preset):

| Band | Est. freq | Standard | Vocal Booster |
|------|-----------|---------|---------------|
| 0 | ~250 Hz | 0 | −4 |
| 1 | ~500 Hz | 0 | 0 |
| 2 | ~1 kHz | 0 | +3 |
| 3 | ~2 kHz | 0 | +2 |
| 4 | ~4 kHz | 0 | +2 |
| 5 | ~6 kHz | 0 | 0 |
| 6 | ~8 kHz | 0 | 0 |

### `0x10` — Primary Device / Multipoint Register

**Read** (empty payload): returns connection state `00 01 01 00` when multipoint is active.

**Write** (6-byte phone MAC): sets this device as the primary, deactivating any other connected device.

```
>> <6 bytes MAC>
<< 00 00 00 00
```

### `0x11` — Unknown

Read-only. Always returns `00 00 00 00`.

### `0x95` — Ready Notification (unsolicited)

Sent **by the headset** immediately after the firmware version response, with no preceding query. Empty payload. Signals that the headset is ready to accept configuration commands.

The app should wait for this notification before sending any writes (`eq_set`, language, multipoint).

## Packet Header Details

### field_0x0A (offset 0x0A, 2 bytes) — CRC16/Maxim

**The headset validates this field per-packet and resets the connection on mismatch.**

```
field_0x0A = CRC16/Maxim(packet[0x0C:])  # seq + body_len + TLV body
```

CRC16/Maxim (Dallas/Maxim 1-Wire): polynomial=0x8005, init=0x0000, refin=True, refout=True, xorout=0xFFFF. Stored as little-endian uint16.

### Correlation ID (offset 0x0C, 4 bytes)

Simple sequence counter. Both sides use independent counters. The phone always sends `01 00 00 00` = 1. The headset uses its own counter in responses. No cross-side matching required — protocol is fully sequential.

### Device List Ordering (`cmd_0x04`)

The currently connected/primary device is always listed at index 0. Index order reflects priority, not insertion order.

## HFP Channel (DLCI 0x08)

Standard HFP 1.8 handshake. Notable vendor extensions:

- `AT+XAPL=0000-0000-0100,7` — Apple accessory protocol; headset responds `+XAPL=iPhone,7`
- `AT+IPHONEACCEV=2,1,<battery>,2,0` — battery level (0–9) reported to phone
- `AT+CSRSF=0,0,0,1,0,0,0` — CSR chip feature query; headset returns `ERROR`

## Connection Sequence

On each connection:

1. HFP negotiation on DLCI `0x08` (BRSF, CIND, CMER, BIND, XAPL, IPHONEACCEV…)
2. Proprietary channel on DLCI `0x1d`:
   - Read firmware version (`0x02`)
   - Read battery (`0x03`)
   - Read EQ state (`0x10`)
   - Read link state (`0x08`)
   - Read paired devices (`0x04`)

## Captures

| File | Contents |
|------|---------|
| `data/cap1/btsnoop_hci.log` | First session: EQ changes, multipoint device management |
| `data/cap1/shokz-bt-capture.zip` | Full bugreport, first session |
| `data/cap1/shokz_dlci1d_raw.txt` | Extracted DLCI 0x1d frames, first session |
| `data/cap2/btsnoop_hci.log` | Second session: multipoint activate/deactivate, language slots |
| `data/cap2/bugreport.zip` | Full bugreport, second session |
| `data/cap2/shokz_dlci1d.txt` | Extracted DLCI 0x1d frames, second session |

## Tools

- `scripts/decode_shokz.py` — decodes DLCI 0x1d frame dumps produced by tshark
