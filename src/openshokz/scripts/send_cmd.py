#!/usr/bin/env python3 -I
"""Send commands to Shokz OpenComm2 (USB-C model) via RFCOMM.

Usage:
  python3 -I scripts/send_cmd.py eq 1 0 0 0 0 0 0 0     # Standard
  python3 -I scripts/send_cmd.py eq 1 4 0 0 0 0 0 0     # Standard + bass boost test
  python3 -I scripts/send_cmd.py eq 2 -4 0 3 2 2 0 0    # Vocal Booster
  python3 -I scripts/send_cmd.py raw 0x0e 01040000000000 # raw hex payload
"""

import socket
import sys
import time

from openshokz.protocol import (
    CMD_FIRMWARE,
    DEFAULT_CHANNEL,
    RESPONSE_BIT,
    build_packet,
    connect,
    drain,
    parse_packet,
)

HEADSET_MAC = "A0:0C:E2:8C:BB:59"
RFCOMM_CHANNEL = DEFAULT_CHANNEL

CMD_EQ = 0x0E
BYTE_MASK = 0xFF

INIT_CMDS = [CMD_FIRMWARE, 0x03, 0x10, 0x08, 0x04]

CMD_BATTERY = 0x03


def _handshake(s: socket.socket) -> None:
    """Send init sequence to prepare headset for config commands."""
    for cmd in INIT_CMDS:
        _ = s.send(build_packet(cmd, b""))
        pkts = drain(s, timeout=0.3)
        for cmd_id, payload in pkts:
            if cmd_id == (RESPONSE_BIT | CMD_FIRMWARE) and payload:
                fw = payload[1:].split(b"\x00")[0].decode("ascii", "replace")
                print(f"  Firmware: {fw}")
            elif cmd_id == (RESPONSE_BIT | CMD_BATTERY) and payload:
                print(f"  Battery: {payload[1]}/9")
    print("  Init complete.")


def main() -> None:
    cli_args = sys.argv[1:]
    if not cli_args:
        print(__doc__)
        sys.exit(1)

    match cli_args[0]:
        case "eq":
            vals = [int(x) for x in cli_args[1:9]]
            if len(vals) != 8:
                print("eq needs 8 values: preset_id b0 b1 b2 b3 b4 b5 b6")
                sys.exit(1)
            payload = bytes([v & BYTE_MASK for v in vals])
            cmd_id = CMD_EQ
        case "raw":
            cmd_id = int(cli_args[1], 16)
            payload = bytes.fromhex(cli_args[2]) if len(cli_args) > 2 else b""
        case _:
            print(__doc__)
            sys.exit(1)

    print(f"Connecting to {HEADSET_MAC} channel {RFCOMM_CHANNEL}...")
    try:
        s = connect(HEADSET_MAC, RFCOMM_CHANNEL)
    except OSError as e:
        sys.exit(f"Connection failed: {e}")

    try:
        print("Connected.")
        _handshake(s)
        pkt = build_packet(cmd_id, payload)
        print(f"Sending cmd=0x{cmd_id:02x} payload={payload.hex()}...")
        _ = s.send(pkt)
        time.sleep(0.5)
        resp_raw = s.recv(256)
        pkts = drain(s, timeout=0.1)
        resp_payload = pkts[0][1] if pkts else b""
        if not resp_payload and resp_raw:
            _, resp_payload = parse_packet(resp_raw)
        print(f"Response: {resp_payload.hex()}")
        if resp_payload == b"\x00\x00\x00\x00":
            print("OK — headset acknowledged")
    except TimeoutError:
        print("No response (timeout)")
    except OSError as e:
        sys.exit(f"Error: {e}")
    finally:
        s.close()


if __name__ == "__main__":
    main()
