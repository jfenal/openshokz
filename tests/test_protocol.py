"""Tests for the Shokz protocol pure functions.

All tests run without hardware — they verify the packet builder,
CRC, parser, and model loader against values from live captures.
"""

import struct
import sys
import textwrap
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from protocol import build_packet, crc16_maxim, parse_packet
from shokz_config import (
    ModelData,
    _as_int,
    _as_str,
    _coerce_model,
    _config_dir,
    _load_presets,
    _load_state,
    _save_presets,
    _save_state,
)


def _firmware_query_inner() -> bytes:
    """Build the inner_content (packet[0x0C:]) for a cmd=0x02 empty query."""
    proto = 2
    body = (
        struct.pack("<III", 2, 4, proto)
        + struct.pack("<III", 3, 4, 0x02)
        + struct.pack("<II", 4, 0)
    )
    return struct.pack("<I", 1) + struct.pack("<I", len(body)) + body


def _eq_vocal_inner() -> bytes:
    """Build inner_content for cmd=0x0e Vocal Booster write."""
    payload = bytes([0x02, 0xFC, 0x00, 0x03, 0x02, 0x02, 0x00, 0x00])
    body = (
        struct.pack("<III", 2, 4, 1)
        + struct.pack("<III", 3, 4, 0x0E)
        + struct.pack("<II", 4, len(payload))
        + payload
    )
    return struct.pack("<I", 1) + struct.pack("<I", len(body)) + body


def _eq_standard_inner() -> bytes:
    """Build inner_content for cmd=0x0e Standard write."""
    payload = bytes([0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
    body = (
        struct.pack("<III", 2, 4, 1)
        + struct.pack("<III", 3, 4, 0x0E)
        + struct.pack("<II", 4, len(payload))
        + payload
    )
    return struct.pack("<I", 1) + struct.pack("<I", len(body)) + body


class TestCrc16Maxim:
    """CRC16/Maxim verified against captured packets."""

    def test_firmware_query(self) -> None:
        # Captured: frame 43720, field_0x0A = 5a b7 = 0xB75A LE
        assert crc16_maxim(_firmware_query_inner()) == 0xB75A

    def test_eq_vocal(self) -> None:
        # Captured: frame 44434, field_0x0A = 5a 7a = 0x7A5A LE
        assert crc16_maxim(_eq_vocal_inner()) == 0x7A5A

    def test_eq_standard(self) -> None:
        # Captured: frame 44787, field_0x0A = c2 18 = 0x18C2 LE
        assert crc16_maxim(_eq_standard_inner()) == 0x18C2

    def test_empty_data(self) -> None:
        # CRC of empty bytes: init=0 XOR 0xFFFF = 0xFFFF
        assert crc16_maxim(b"") == 0xFFFF

    def test_single_byte(self) -> None:
        result = crc16_maxim(b"\x00")
        assert 0 <= result <= 0xFFFF

    def test_different_inputs_differ(self) -> None:
        assert crc16_maxim(b"\x01") != crc16_maxim(b"\x02")

    def test_reproducible(self) -> None:
        raw = b"\xde\xad\xbe\xef"
        assert crc16_maxim(raw) == crc16_maxim(raw)


_CAPTURED_FW_QUERY = bytes.fromhex(
    "a55a2c000100000028005ab701000000"
    + "200000000200000004000000020000000300000004000000020000000400000000000000"
)
_CAPTURED_EQ_VOCAL = bytes.fromhex(
    "a55a34000100000030005a7a010000002800000002000000040000000100000003000000"
    + "040000000e000000040000000800000002fc000302020000"
)
_CAPTURED_EQ_STANDARD = bytes.fromhex(
    "a55a3400010000003000c218010000002800000002000000040000000100000003000000"
    + "040000000e00000004000000080000000100000000000000"
)


class TestBuildPacket:
    """build_packet() must reproduce exact captured bytes byte-for-byte."""

    def test_firmware_query_exact(self) -> None:
        pkt = build_packet(0x02, b"")
        assert pkt == _CAPTURED_FW_QUERY, (
            f"Firmware query mismatch:\n  got: {pkt.hex()}\n  want: {_CAPTURED_FW_QUERY.hex()}"
        )

    def test_eq_vocal_exact(self) -> None:
        payload = bytes([0x02, 0xFC, 0x00, 0x03, 0x02, 0x02, 0x00, 0x00])
        assert build_packet(0x0E, payload) == _CAPTURED_EQ_VOCAL

    def test_eq_standard_exact(self) -> None:
        payload = bytes([0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        assert build_packet(0x0E, payload) == _CAPTURED_EQ_STANDARD

    def test_magic_header(self) -> None:
        assert build_packet(0x02, b"")[:2] == b"\xa5\x5a"

    def test_direction_flag_read(self) -> None:
        assert build_packet(0x02, b"")[4:8] == b"\x01\x00\x00\x00"

    def test_proto_ver_read_is_2(self) -> None:
        # Body at 0x14; tag=2 TLV: tag(4) + len(4) + value(4) -> value at 0x14+8=0x1C
        val = struct.unpack_from("<I", build_packet(0x02, b""), 0x1C)[0]
        assert val == 2

    def test_proto_ver_write_is_1(self) -> None:
        eq_pkt = build_packet(0x0E, b"\x01\x00\x00\x00\x00\x00\x00\x00")
        assert struct.unpack_from("<I", eq_pkt, 0x1C)[0] == 1

    def test_crc_in_field_position(self) -> None:
        pkt = build_packet(0x02, b"")
        field = struct.unpack_from("<H", pkt, 0x0A)[0]
        assert field == crc16_maxim(pkt[0x0C:])

    def test_outer_len_consistent(self) -> None:
        pkt = build_packet(0x03, b"")
        assert struct.unpack_from("<H", pkt, 2)[0] == len(pkt) - 8

    def test_different_cmd_ids_differ(self) -> None:
        assert build_packet(0x02, b"") != build_packet(0x03, b"")

    def test_different_payloads_differ(self) -> None:
        p1 = bytes([0x01, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        p2 = bytes([0x02, 0xFC, 0x00, 0x03, 0x02, 0x02, 0x00, 0x00])
        assert build_packet(0x0E, p1) != build_packet(0x0E, p2)


_CAPTURED_FW_RESPONSE = bytes.fromhex(
    "a55a4f00010100004b005833010000004300000002000000040000000200000003000000"
    + "040000000280000004000000230000000048435f48555f565f30315f32303235313131"
    + "36000000000000000000000000000000000000"
)


class TestParsePacket:
    """parse_packet() correctly extracts cmd_id and payload."""

    def test_firmware_response_cmd_id(self) -> None:
        cmd_id, _ = parse_packet(_CAPTURED_FW_RESPONSE)
        assert cmd_id == 0x8002

    def test_firmware_response_payload_contains_version(self) -> None:
        _, payload = parse_packet(_CAPTURED_FW_RESPONSE)
        assert b"HC_HU_V_01_20251116" in payload

    def test_firmware_response_payload_starts_null(self) -> None:
        _, payload = parse_packet(_CAPTURED_FW_RESPONSE)
        assert payload[0] == 0x00
        assert payload[1:].split(b"\x00")[0].decode("ascii") == "HC_HU_V_01_20251116"

    def test_round_trip_read(self) -> None:
        pkt = build_packet(0x03, b"")
        cmd_id, payload = parse_packet(pkt)
        assert cmd_id == 0x03
        assert payload == b""

    def test_round_trip_write(self) -> None:
        eq_payload = bytes([0x01, 0x04, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00])
        pkt = build_packet(0x0E, eq_payload)
        cmd_id, payload = parse_packet(pkt)
        assert cmd_id == 0x0E
        assert payload == eq_payload

    def test_invalid_magic_returns_minus1(self) -> None:
        cmd_id, payload = parse_packet(b"\x00" * 20)
        assert cmd_id == -1
        assert payload == b""

    def test_too_short_returns_minus1(self) -> None:
        cmd_id, payload = parse_packet(b"\xa5\x5a\x04\x00")
        assert cmd_id == -1
        assert payload == b""

    def test_parse_firmware_query(self) -> None:
        cmd_id, payload = parse_packet(_CAPTURED_FW_QUERY)
        assert cmd_id == 0x02
        assert payload == b""


class TestCoercionHelpers:
    def test_as_int_int(self) -> None:
        assert _as_int(14) == 14

    def test_as_int_str(self) -> None:
        # YAML parses hex literals (0x0e) as ints automatically;
        # _as_int handles plain decimal strings
        assert _as_int("14", 0) == 14

    def test_as_int_invalid(self) -> None:
        assert _as_int("nope", 99) == 99

    def test_as_int_none(self) -> None:
        assert _as_int(None, 7) == 7

    def test_as_str_value(self) -> None:
        assert _as_str("hello") == "hello"

    def test_as_str_none(self) -> None:
        assert _as_str(None, "default") == "default"

    def test_as_str_int_coerced(self) -> None:
        assert _as_str(42) == "42"


_MINIMAL_YAML = textwrap.dedent("""\
    name: "Test Headset"
    firmware_prefix: "HC_HU"
    oui_prefixes:
      - "a0:0c:e2"
    bluetooth:
      rfcomm_channel: 14
    battery:
      command: 0x03
      scale: 9
    eq:
      command: 0x0e
      preset_id_byte: 0
      band_bytes: [1, 2, 3, 4, 5, 6, 7]
      custom_preset_id: 1
      presets:
        standard:
          id: 1
          bands: [0, 0, 0, 0, 0, 0, 0]
          label: "Standard"
        vocal:
          id: 2
          bands: [-4, 0, 3, 2, 2, 0, 0]
          label: "Vocal Booster"
    language:
      command: 0x02
      codes:
        en: 0x00
        zh: 0x01
        ja: 0x02
        ko: 0x03
    device_info:
      command: 0x04
    multipoint:
      add_command: 0x0b
      primary_command: 0x10
""")


class TestModelLoader:
    @pytest.fixture()
    def model(self) -> ModelData:
        return _coerce_model(yaml.safe_load(_MINIMAL_YAML))

    def test_name(self, model: ModelData) -> None:
        assert model.get("name") == "Test Headset"

    def test_firmware_prefix(self, model: ModelData) -> None:
        assert model.get("firmware_prefix") == "HC_HU"

    def test_oui_prefixes(self, model: ModelData) -> None:
        assert model.get("oui_prefixes") == ["a0:0c:e2"]

    def test_rfcomm_channel(self, model: ModelData) -> None:
        assert model.get("bluetooth", {}).get("rfcomm_channel") == 14

    def test_battery_command(self, model: ModelData) -> None:
        assert model.get("battery", {}).get("command") == 3

    def test_battery_scale(self, model: ModelData) -> None:
        assert model.get("battery", {}).get("scale") == 9

    def test_eq_command(self, model: ModelData) -> None:
        assert model.get("eq", {}).get("command") == 14

    def test_eq_presets_exist(self, model: ModelData) -> None:
        presets = model.get("eq", {}).get("presets", {})
        assert "standard" in presets
        assert "vocal" in presets

    def test_eq_standard_bands_flat(self, model: ModelData) -> None:
        bands = model.get("eq", {}).get("presets", {}).get("standard", {}).get("bands", [])
        assert bands == [0, 0, 0, 0, 0, 0, 0]

    def test_eq_vocal_bands(self, model: ModelData) -> None:
        bands = model.get("eq", {}).get("presets", {}).get("vocal", {}).get("bands", [])
        assert bands == [-4, 0, 3, 2, 2, 0, 0]

    def test_language_codes(self, model: ModelData) -> None:
        codes = model.get("language", {}).get("codes", {})
        assert codes.get("en") == 0
        assert codes.get("zh") == 1
        assert codes.get("ja") == 2
        assert codes.get("ko") == 3

    def test_multipoint_commands(self, model: ModelData) -> None:
        mp = model.get("multipoint", {})
        assert mp.get("add_command") == 0x0B
        assert mp.get("primary_command") == 0x10

    def test_invalid_model_raises(self) -> None:
        with pytest.raises(ValueError, match="YAML mapping"):
            _coerce_model("not a dict")

    def test_unknown_keys_ignored(self) -> None:
        raw = yaml.safe_load(_MINIMAL_YAML)
        assert isinstance(raw, dict)
        raw["unknown_key"] = "ignored"
        model = _coerce_model(raw)
        assert "unknown_key" not in model

    def test_missing_optional_keys(self) -> None:
        raw = yaml.safe_load("name: X\nfirmware_prefix: TEST\n")
        model = _coerce_model(raw)
        assert model.get("name") == "X"
        assert "eq" not in model


class TestOpenComm2Model:
    """Load the real model file and verify its contents."""

    @pytest.fixture()
    def model_path(self) -> Path:
        p = Path(__file__).parent.parent / "models" / "opencomm2_2025.yaml"
        if not p.exists():
            pytest.skip("models/opencomm2_2025.yaml not found")
        return p

    @pytest.fixture()
    def model(self, model_path: Path) -> ModelData:
        with model_path.open() as f:
            return _coerce_model(yaml.safe_load(f))

    def test_firmware_prefix(self, model: ModelData) -> None:
        assert model.get("firmware_prefix") == "HC_HU"

    def test_rfcomm_channel(self, model: ModelData) -> None:
        assert model.get("bluetooth", {}).get("rfcomm_channel") == 14

    def test_has_standard_preset(self, model: ModelData) -> None:
        assert "standard" in model.get("eq", {}).get("presets", {})

    def test_standard_is_flat(self, model: ModelData) -> None:
        bands = model.get("eq", {}).get("presets", {}).get("standard", {}).get("bands", [])
        assert all(b == 0 for b in bands)

    def test_vocal_eq_shape(self, model: ModelData) -> None:
        bands = model.get("eq", {}).get("presets", {}).get("vocal", {}).get("bands", [])
        assert bands[0] < 0
        assert any(b > 0 for b in bands[2:5])

    def test_language_has_en(self, model: ModelData) -> None:
        assert model.get("language", {}).get("codes", {}).get("en") == 0

    def test_oui_prefix_is_shokz(self, model: ModelData) -> None:
        ouis = model.get("oui_prefixes", [])
        assert any("a0:0c:e2" in oui.lower() for oui in ouis)


# ── Battery percentage formula ────────────────────────────────────────────────


class TestBatteryFormula:
    """Battery percentage formula: min(100, (level+1) * (100//(scale+1))).

    Verified against phone app (Shokz app showed 40% when level=3, scale=9).
    Each level represents a 10-percentage-point step on the 0-9 scale.
    """

    def _pct(self, level: int, scale: int = 9) -> int:
        return min(100, (level + 1) * (100 // (scale + 1)))

    def test_full_battery(self) -> None:
        assert self._pct(9) == 100

    def test_40_percent_matches_phone(self) -> None:
        assert self._pct(3) == 40

    def test_10_percent_steps(self) -> None:
        expected = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100]
        assert [self._pct(i) for i in range(10)] == expected

    def test_zero_level(self) -> None:
        assert self._pct(0) == 10

    def test_capped_at_100(self) -> None:
        assert self._pct(9) == 100
        assert self._pct(9) <= 100


class TestPresetStorage:
    def test_load_presets_missing_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("HOME", str(tmp_path))
        assert _load_presets() == []

    def test_save_and_load_presets(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HOME", str(tmp_path))
        presets: list[dict[str, object]] = [{"name": "My Bass", "bands": [4, 0, 0, 0, 0, 0, 0]}]
        _save_presets(presets)
        assert _load_presets() == presets

    def test_save_state_and_load(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HOME", str(tmp_path))
        _save_state("vocal")
        assert _load_state()["active_eq"] == "vocal"

    def test_save_state_atomic(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("HOME", str(tmp_path))
        _save_state("standard")
        assert not (_config_dir() / "state.json.tmp").exists()
