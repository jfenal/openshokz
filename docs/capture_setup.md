# Capturing Bluetooth Traffic for Reverse Engineering

To add support for a new Shokz model, you need to observe what commands the
official Android app sends to the headset. This guide walks through the capture
workflow on Android.

## What you need

- Android phone (any version) with the Shokz app installed
- USB cable + a computer with `adb` installed
- Wireshark or `tshark` for analysis

## Step 1 — Enable HCI snoop logging on the phone

1. **Settings → About phone** → tap **Build number** 7 times → Developer Options unlocked
2. **Settings → Developer Options** → enable **Bluetooth HCI snoop log**
3. Toggle Bluetooth **off then on** to start a fresh log session

## Step 2 — Connect the phone via USB

1. Plug in the USB cable
2. On the phone, pull down the notification shade → tap the USB notification →
   select **File Transfer** (not Charging only)
3. A prompt appears: **"Allow USB debugging?"** → tap **Allow**
4. Verify the phone is visible:

```bash
adb devices
# Should show:  XXXXXXXX   device
```

## Step 3 — Capture a session

1. Connect your headset to the phone via the Shokz app
2. Exercise the features you want to reverse-engineer:
   - Change EQ presets (one at a time, pause between each)
   - Change language slots
   - Toggle multipoint
   - Check battery
3. Pull the Bluetooth HCI log:

```bash
adb bugreport /tmp/shokz-capture.zip
```

This takes 30–90 seconds. The log is inside the zip.

## Step 4 — Extract and decode

```bash
# Extract the HCI log from the bugreport
7z e /tmp/shokz-capture.zip "FS/data/log/bt/btsnoop_hci.log" -o/tmp/shokz/

# Extract DLCI 0x1d (proprietary SPP channel) frames for your headset MAC
# Replace A0:0C:E2:8C:BB:59 with your headset's MAC address
tshark -r /tmp/shokz/btsnoop_hci.log \
  -Y "btrfcomm.dlci == 0x1d && (bthci_acl.src.bd_addr == a0:0c:e2:8c:bb:59 || \
       bthci_acl.dst.bd_addr == a0:0c:e2:8c:bb:59)" \
  -T fields -e frame.number -e frame.time_relative \
  -e bthci_acl.src.bd_addr -e bthci_acl.dst.bd_addr -e data.data \
  > /tmp/shokz/frames.txt

# Decode the frames
python3 -I scripts/decode_shokz.py /tmp/shokz/frames.txt
```

## Step 5 — Generate a model template

```bash
# Connect the headset to your computer (not the phone)
python3 -I scripts/probe_model.py
# → writes models/<FIRMWARE_PREFIX>.yaml.template
```

Fill in the template with the preset names and language codes you observed in
the capture, then follow [contributing.md](contributing.md) to open a PR.

## Tips

- Make **one change at a time** in the Shokz app, then pause 2 seconds before the next.
  The decode script shows timestamps — this makes it easy to correlate each UI action
  with the command that was sent.

- The first ~20 frames after connection are always the same initialization sequence
  (firmware version query, battery, device info). The interesting frames come after.

- Write-only commands (EQ, language) appear as frames with `proto_ver=1` in the
  decoded output. Read-only commands (battery, device info) have `proto_ver=2`.

- The `field_0x0A` in each packet is `CRC16/Maxim(packet[0x0C:])`. The `_build()`
  function in `protocol.py` computes it automatically — you don't need to handle it
  manually.

## Finding your headset MAC

```bash
bluetoothctl info  # lists all paired devices with MACs
```

Or check the decode output — the headset's MAC appears as the source address in
responses.

## Multiple captures

Save each session with a descriptive name:

```bash
adb bugreport /tmp/shokz-eq-session.zip
adb bugreport /tmp/shokz-lang-session.zip
```

Keep the raw `.zip` files alongside the extracted `.log` and decoded frame
dumps — they're useful for going back and checking edge cases.
