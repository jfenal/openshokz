"""Shokz BT protocol constants and low-level packet functions."""

import socket
import struct

RFCOMM_PROTO: int = socket.BTPROTO_RFCOMM

MAGIC = b"\xa5\x5a"
BODY_OFFSET = 0x14
HEADER_SIZE = 8
CRC_POLY_REFLECTED = 0xA001
CRC_XOROUT = 0xFFFF
RESPONSE_BIT = 0x8000

TAG_PROTO_VER = 2
TAG_CMD_ID = 3
TAG_PAYLOAD = 4

WRITE = 1
READ = 2

DEFAULT_CHANNEL = 14

CMD_FIRMWARE = 0x02


def crc16_maxim(raw: bytes) -> int:
    """CRC16/Maxim: poly=0x8005, init=0, refin, refout, xorout=0xFFFF."""
    crc = 0
    for b in raw:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ CRC_POLY_REFLECTED if crc & 1 else crc >> 1
    return crc ^ CRC_XOROUT


def build_packet(cmd_id: int, payload: bytes, corr: int = 1) -> bytes:
    """Build a Shokz RFCOMM command packet with CRC16/Maxim authentication."""
    proto = WRITE if payload else READ
    body = (
        struct.pack("<III", TAG_PROTO_VER, 4, proto)
        + struct.pack("<III", TAG_CMD_ID, 4, cmd_id)
        + struct.pack("<II", TAG_PAYLOAD, len(payload))
        + payload
    )
    inner = struct.pack("<I", corr) + struct.pack("<I", len(body)) + body
    field = struct.pack("<H", crc16_maxim(inner))
    outer_len = len(inner) + 4
    hdr = MAGIC + struct.pack("<H", outer_len) + b"\x01\x00\x00\x00"
    return hdr + struct.pack("<H", len(inner)) + field + inner


def parse_packet(raw: bytes) -> tuple[int, bytes]:
    """Parse a Shokz RFCOMM packet. Returns (cmd_id, payload), or (-1, b'') on error."""
    if len(raw) < BODY_OFFSET or raw[:2] != MAGIC:
        return -1, b""
    body_len = struct.unpack_from("<I", raw, 0x10)[0]
    body = raw[BODY_OFFSET : BODY_OFFSET + body_len]
    i, cmd_id, payload = 0, -1, b""
    while i + 8 <= len(body):
        tag = struct.unpack_from("<I", body, i)[0]
        length = struct.unpack_from("<I", body, i + 4)[0]
        i += 8
        val = body[i : i + length]
        i += length
        if tag == TAG_CMD_ID and len(val) >= 4:
            cmd_id = struct.unpack_from("<I", val)[0]
        elif tag == TAG_PAYLOAD:
            payload = val
    return cmd_id, payload


def drain(s: socket.socket, timeout: float = 2.0) -> list[tuple[int, bytes]]:
    """Receive all pending Shokz packets within timeout."""
    s.settimeout(timeout)
    buf: bytes = b""
    results: list[tuple[int, bytes]] = []
    while True:
        try:
            chunk = s.recv(512)
            if not chunk:
                break
            buf += chunk
        except (TimeoutError, OSError):
            break
        while len(buf) >= 4:
            if buf[:2] != MAGIC:
                buf = buf[1:]
                continue
            frame_size = struct.unpack_from("<H", buf, 2)[0] + HEADER_SIZE
            if len(buf) < frame_size:
                break
            results.append(parse_packet(buf[:frame_size]))
            buf = buf[frame_size:]
    return results


def connect(mac: str, channel: int) -> socket.socket:
    """Open an RFCOMM connection to the headset."""
    s = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, RFCOMM_PROTO)
    s.settimeout(2)
    s.connect((mac, channel))
    return s
