# TODO

## Protocol unknowns

- [x] **field_0x0A formula found**: `CRC16/Maxim(packet[0x0C:])` stored as little-endian
  uint16. CRC16/Maxim: poly=0x8005, init=0x0000, refin=True, refout=True, xorout=0xFFFF.
  Confirmed 60/61 captured packets match. Implemented in `shokz_config.py::_crc16_maxim`.

- [x] **Custom EQ band values confirmed**: headset DSP applies the 7 signed-byte band
  values directly. Preset ID 0x01 (Standard) or 0x02 (Vocal) must be used; the ID
  determines only which voice prompt plays. Arbitrary band values work.

- [ ] **Map `cmd_0x03` byte 2 (`0xff` at 100% charge)**: recapture when battery is below
  full to see if this byte encodes charging state or a second battery level.

- [ ] **Determine full multipoint deactivation command**: the ACL-level disconnect theory
  needs confirmation. Capture with Wireshark HCI filter on L2CAP disconnect events
  timed against the Shokz app's "disable multipoint" action.

- [ ] **Identify language slot commit mechanism**: the trailing `00 00 00 00` write after
  language slot writes may be a commit signal or just an English reset tap. Capture a
  session where only 2 language slots are set (no trailing tap) to confirm.

- [ ] **Unknown commands**: `cmd_0x06`, `cmd_0x08`, `cmd_0x11` always return `00 00 00 00`.
  Purpose unknown. Try writing non-zero values to observe effect.

## Firmware

- [ ] **Download firmware binary**: the firmware update API requires Bearer auth (Shokz
  account login). API endpoint: `GET https://app.shokz.com/app/firmware/HC_HU/latest`
  (served from AWS EU-Central-1, `3.126.119.158`). Response includes CDN URL for the
  binary (likely `appcdn.shokz.com/...`). OTA delivery to headset uses Jieli CD03 BT
  protocol (Jieli CD03 BT OTA). To get the binary:
  intercept HTTPS from Shokz app (requires device cert trust or root + Frida).
  Current installed firmware: `HC_HU_V_01_20251116`.

- [x] **Auto-off not present**: exhaustive probe of 0x00–0xFF plus app-referenced IDs
  (0x05, 0x0d, 0x5D, 0x86, 0x9A, 0x100, 0x10FF) all returned no-response. The app's
  shared Shokz SDK references these for other models; the OpenComm2 2025 firmware
  does not implement them. No auto-off command exists for this device.
