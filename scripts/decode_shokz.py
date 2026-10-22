#!/usr/bin/env python3 -I
"""Decode Shokz RFCOMM DLCI 0x1d proprietary protocol frames.

Usage: python3 -I scripts/decode_shokz.py data/shokz_dlci1d_raw.txt

Packet structure (all LE):
  a5 5a           - magic
  XX 00           - payload length (after first 4 bytes)
  01 00 / 01 01   - direction: 00=query, 01=response
  00 00           - padding
  XX 00           - message length
  XX XX XX XX XX XX  - correlation ID (6 bytes)
  XX 00 00 00     - body container length
  TLV entries:
    tag  (4 bytes) | len (4 bytes) | value (len bytes)
    tag=2: protocol version (always 2)
    tag=3: command ID (high byte 0x80 = response)
    tag=4: payload data
"""

import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from protocol import BODY_OFFSET, MAGIC, RESPONSE_BIT, TAG_CMD_ID, TAG_PAYLOAD

RESPONSE_BIT_MASK = RESPONSE_BIT - 1  # strips the response bit: 0x7FFF
HEADSET_OUI = "a0:0c:e2"

COMMANDS = {
    # empty read -> firmware version string
    # write XX 00 00 00 -> set language slot (echo response)
    # lang codes: 00=English, 01=Chinese, 02=Japanese, 03=Korean
    0x02: "firmware_or_language",
    # 00 <level:0-9> <ff?> 00  (9=100%, matches AT+IPHONEACCEV scale)
    0x03: "battery",
    0x04: "device_info",
    0x06: "unknown_06",
    0x08: "unknown_08",
    0x0B: "device_lookup",
    0x0C: "unknown_0c",
    0x0D: "unknown_0d",
    # write: byte0=preset_id, bytes1-7=signed EQ bands (dB)
    # 0x01=Standard (flat), 0x02=Vocal Booster (-4,0,+3,+2,+2,0,0)
    # OpenComm2 (USB-C model) has only these 2 presets
    0x0E: "eq_set",
    0x0F: "unknown_0f",
    # writable with MAC: registers/trusts a device
    0x10: "device_register",
    0x11: "unknown_11",
    0x14: "unknown_14",
}


def parse_tlvs(tlv_bytes: bytes) -> list[tuple[int, bytes]]:
    tlvs = []
    i = 0
    while i + 8 <= len(tlv_bytes):
        tag = struct.unpack_from("<I", tlv_bytes, i)[0]
        length = struct.unpack_from("<I", tlv_bytes, i + 4)[0]
        i += 8
        value = tlv_bytes[i : i + length]
        i += length
        tlvs.append((tag, value))
    return tlvs


MIN_FRAME_HEADER = 12  # magic(2) + outer_len(2) + direction(4) + inner_len(2) + crc(2)


def decode_frame(hex_str: str, src: str, frame: str, timestamp: str) -> None:
    raw = bytes.fromhex(hex_str)
    if len(raw) < MIN_FRAME_HEADER or raw[:2] != MAGIC:
        return

    is_response = raw[5] == 0x01

    if len(raw) < BODY_OFFSET:
        return
    body_len = struct.unpack_from("<I", raw, 0x10)[0]
    body = raw[BODY_OFFSET : BODY_OFFSET + body_len]

    tlvs = parse_tlvs(body)
    cmd_id = None
    payload = b""
    for tag, value in tlvs:
        if tag == TAG_CMD_ID:
            raw_cmd = struct.unpack_from("<I", value)[0] if len(value) >= 4 else 0
            cmd_id = raw_cmd & RESPONSE_BIT_MASK
        elif tag == TAG_PAYLOAD:
            payload = value

    direction = "<<" if is_response else ">>"
    cmd_name = COMMANDS.get(cmd_id, f"cmd_0x{cmd_id:02x}") if cmd_id is not None else "?"
    payload_hex = payload.hex() if payload else "(empty)"

    ts = f"{float(timestamp):>10.3f}s"
    print(f"  {frame:>6} t={ts} {direction} [{cmd_name}] payload={payload_hex}")


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else "data/shokz_dlci1d_raw.txt"
    with open(path) as f:
        for line in f:
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 5:
                continue
            frame, timestamp, src, _dst, hex_data = (
                parts[0],
                parts[1],
                parts[2],
                parts[3],
                parts[4],
            )
            if not hex_data:
                continue
            is_headset_src = src.lower().startswith(HEADSET_OUI)
            direction_byte = int(hex_data[8:10], 16) if len(hex_data) >= 10 else 0
            is_response = direction_byte == 0x01
            if not is_response and not is_headset_src:
                print()
            decode_frame(hex_data, src, frame, timestamp)


if __name__ == "__main__":
    main()
