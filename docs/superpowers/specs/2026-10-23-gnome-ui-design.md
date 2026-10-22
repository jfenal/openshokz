# openshokz GNOME UI — Design

Date: 2026-10-23

## Intent and why

openshokz has a working CLI. The goal is to make it accessible as a native
GNOME app for day-to-day configuration and a shell extension for quick EQ
switching without opening a settings window.

## Goals

- GTK4 + libadwaita settings app: single scrolling page, full config
- GNOME Shell Extension: top-bar indicator with battery %, click to flip EQ preset
- Custom presets: 3 user-named EQ presets persisted locally, visible in both
  the app and the extension popup
- No daemon: both the app and extension call the existing `openshokz` CLI directly

## Non-goals

- Packaging (Flatpak, RPM) — out of scope for this iteration
- macOS / Windows support
- Real-time waveform or spectrum display
- Bluetooth device pairing or discovery (already handled by GNOME Settings)

## Anti-goals

- A "smart" background service that auto-applies settings — keep it explicit
- Cloud sync of presets

---

## Part 1 — GTK4/Adwaita Settings App

### Entry point

`openshokz-app` binary (or `python3 -I openshokz_app.py`), separate from the
CLI. Launches a `GtkApplication` + `AdwApplicationWindow`.

### Layout

Single `AdwPreferencesPage` with four `AdwPreferencesGroup` sections, in order:

1. **Device** — firmware string, battery with progress bar, paired device list
2. **EQ Preset** — preset chips + "Add" button
3. **Language Priority** — 4 draggable rows
4. **Paired Devices** — connected and paired device names (read-only)

No sidebar, no tabs. All sections visible on one scroll.

### Section: Device

Header row showing model name, firmware version (secondary text), and battery
level (right-aligned, green `●` + percentage). This is read-only; populated
at app open by running `openshokz info`.

### Section: EQ Preset

A horizontal wrapping row of pill/chip buttons: Standard, Vocal Booster
(from the model YAML), then up to 3 custom presets (from local JSON), then a
`+` Add button.

- Tapping a built-in preset → immediately sends the command, highlights that
  chip
- Tapping a custom preset → immediately sends; long-press or pencil icon →
  opens Edit Preset sub-page
- `+` Add → opens Edit Preset sub-page with blank name and flat bands

**Edit Preset sub-page** (`AdwNavigationPage`):
- `AdwEntryRow` for the preset name
- 7 `GtkScale` sliders (horizontal, −12 to +12 dB), one per band, labelled
  250 Hz / 500 Hz / 1 kHz / 2 kHz / 4 kHz / 6 kHz / 8 kHz
- "Apply & Save" button → sends to headset + writes to local JSON
- "Delete" button (for existing presets only, destructive style)

### Section: Language Priority

`AdwPreferencesGroup` containing a `GtkListBox` with 4 `AdwActionRow`s (one
per language). Each row has a drag handle suffix widget. Dragging reorders the
list visually. An "Apply order" `AdwButtonRow` at the bottom sends the new
order to the headset.

Languages are fixed: English (en), Chinese (zh), Korean (ko), Japanese (ja).
No adding or removing — just reordering.

### Local preset storage

`~/.config/openshokz/presets.json` — array of objects:

```json
[
  {"name": "My Bass", "bands": [4, 0, 0, 0, 0, 0, 0]},
  {"name": "Presence", "bands": [0, 0, 2, 3, 2, 0, 0]},
  {"name": "Flat+",   "bands": [0, 0, 0, 0, 0, 0, 0]}
]
```

Max 3 entries. The CLI's `eq custom` subcommand is extended to accept a
preset name from this file: `openshokz eq custom "My Bass"`.

### Sending commands

The app calls `openshokz` as a subprocess (via `GLib.spawn_async` or
`Gio.Subprocess`). It does not link against the Python code directly. This
keeps the GTK app thin: it is a UI shell over the existing CLI.

Error handling: if the subprocess fails (headset not connected), show an
`AdwToast` with the error message. Do not crash.

---

## Part 2 — GNOME Shell Extension

### Indicator

A `SystemIndicator` in the status area showing `🎧 NN%` (headphone emoji +
battery percentage). Updates on first open by running
`openshokz info --short` and parsing the battery line.

Battery polling: every 5 minutes via `GLib.timeout_add_seconds`. Not on every
click — too slow (3 s handshake).

### Popup menu

Clicking the indicator opens a `St.BoxLayout` popup with:

1. Model name + battery bar (header, non-interactive)
2. **EQ PRESET** label
3. One `St.Button` per preset (2 built-in + up to 3 custom) — active preset
   highlighted in accent colour. Custom preset names loaded from
   `~/.config/openshokz/presets.json` at startup and whenever the file
   changes (watch via `Gio.FileMonitor`).
4. **Open Settings →** button — launches the GTK4 app via
   `GLib.spawn_command_line_async("openshokz-app")`

### EQ switching

Clicking a preset button runs `openshokz eq <preset>` via
`Gio.Subprocess`. The UI optimistically highlights the selected preset
immediately; if the subprocess exits non-zero, reverts and shows a brief
error notification.

3-second switch time is acceptable for deliberate action.

### Extension structure

```
gnome-extension/
  extension.js       main extension code
  metadata.json      UUID, GNOME Shell version range
  stylesheet.css     minimal style overrides
  prefs.js           (empty for now — no user prefs)
```

UUID: `openshokz@jfenal.github.com`

---

## Constraints

- Python 3.11+ for the GTK app (`gi.repository.Adw`, `gi.repository.Gtk`)
- GJS (GNOME JavaScript) for the extension — no Python in the extension itself
- `openshokz` CLI must be on `$PATH`; app shows an error dialog if not found
- GNOME Shell 45+ (uses modern extension API)
- No root required

---

## Active preset state

The headset has no read command for the current EQ preset (`cmd_0x0e` is
write-only). Active preset is tracked in a local state file:

`~/.config/openshokz/state.json`:
```json
{"active_eq": "vocal", "updated": "2026-10-23T09:15:00"}
```

The CLI writes this file every time `openshokz eq` applies a preset. The app
and extension read it on open to highlight the right chip. If the file is
absent (first run), no preset is highlighted.

Note: if the user applies a preset via the official Shokz app, the state file
goes stale. This is a known limitation, documented in the UI as a tooltip.

## Headset connectivity

At startup (app and extension), run `openshokz info` as a subprocess to
detect headset reachability:

- **Reachable**: populate device section with live data, enable all controls
- **Unreachable**: show an `AdwBanner` ("Headset not connected") at the top,
  grey out (insensitive) all interactive widgets — EQ chips, Language Apply
  button, Edit Preset. Device section shows last-known values or dashes.

The extension indicator shows `🎧 --` when disconnected. The popup still
opens but EQ buttons are insensitive, with a "Not connected" label at the top.

Recheck: the app rechecks on window focus. The extension rechecks on every
popup open (in addition to the 5-minute battery poll).

## CLI additions needed before UI

Before building the UI, the CLI needs two additions:

1. `openshokz eq list --json` — prints all presets (built-in + custom from
   `presets.json`) as JSON. Used by the GJS extension which cannot parse YAML.
   ```json
   [
     {"name": "Standard",      "builtin": true,  "arg": "standard"},
     {"name": "Vocal Booster", "builtin": true,  "arg": "vocal"},
     {"name": "My Bass",       "builtin": false, "arg": "My Bass"},
     {"name": "Presence",      "builtin": false, "arg": "Presence"},
     {"name": "Flat+",         "builtin": false, "arg": "Flat+"}
   ]
   ```

2. `openshokz eq "My Bass"` — look up name in `presets.json`, resolve to band
   values, apply. The app and extension only need to pass the preset name; the
   CLI handles the lookup.

## Left to the builder

- Exact `AdwPreferencesGroup` / `AdwActionRow` widget hierarchy for the
  drag-reorder list (GTK4 drag-and-drop API for listbox rows)
- Whether to use `Adw.NavigationView` or a separate `Adw.Dialog` for Edit
  Preset — both work; pick whichever is simpler
- CSS class choices for the EQ chip active state
- Extension metadata GNOME Shell version range (target 45–47)
- Whether `openshokz info --short` is a new CLI flag or parsed from existing
  output (builder's call)
