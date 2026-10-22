# GNOME Shell Extension Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A GNOME Shell Extension that shows a 🎧 battery indicator in the top bar and a popup with all EQ presets (built-in + custom) for quick switching.

**Architecture:** A `SystemIndicator` with a `St.Label` showing battery %. Clicking opens a `QuickSettingsMenu` with preset buttons. Presets loaded via `openshokz eq list --json` subprocess on popup open. Active preset from `~/.config/openshokz/state.json` (watched with `Gio.FileMonitor`). EQ switch via `openshokz eq "<name>"` subprocess. Battery polled every 5 minutes.

**Tech Stack:** GJS (GNOME JavaScript), GNOME Shell 45+, `Gio.Subprocess`, `GLib.timeout_add_seconds`. No Python in the extension.

**Spec:** `docs/superpowers/specs/2026-10-23-gnome-ui-design.md` — Part 2.

**Prerequisite:** `docs/superpowers/plans/2026-10-23-cli-additions.md` must be complete.

## Global Constraints

- UUID: `openshokz@jfenal.github.com`
- Target GNOME Shell 45–47 (`"shell-version": ["45", "46", "47"]` in metadata)
- No Python, no external npm — pure GJS + GNOME Shell APIs
- `openshokz` binary must be found via `GLib.find_program_in_path("openshokz")` — indicator hidden if not found
- Battery poll: every 300 seconds (5 minutes) via `GLib.timeout_add_seconds`
- State file watched with `Gio.FileMonitor` — active preset updates without polling
- "Open Settings" launches `openshokz-app` if found, else opens a terminal with the CLI hint

## Review Focus

- **`openshokz` not on PATH** — indicator must not appear rather than crash; check `GLib.find_program_in_path` in `enable()`.
- **State file absent on first load** — no preset highlighted; popup renders correctly.
- **Subprocess takes > 3 s** — the popup should not freeze GNOME Shell; use async subprocess (`Gio.Subprocess` with `communicate_async`), never synchronous.
- **Extension disabled while subprocess running** — `disable()` must cancel any in-flight subprocess and timeout.
- **GNOME Shell upgrade** — extension should fail gracefully (no crash) if Shell API changes; wrap in try/catch where volatile.

---

### Task 1: Extension scaffold and metadata

**Files:**
- Create: `gnome-extension/metadata.json`
- Create: `gnome-extension/extension.js` — skeleton with `enable()` / `disable()`
- Create: `gnome-extension/stylesheet.css` — empty for now

**Interfaces:**
- Produces: installable extension skeleton (no indicator yet)

- [ ] **Step 1: Create `metadata.json`**

```json
{
  "name": "openshokz",
  "description": "Shokz headset EQ switcher and battery indicator",
  "uuid": "openshokz@jfenal.github.com",
  "shell-version": ["45", "46", "47"],
  "version": 1,
  "url": "https://github.com/jfenal/openshokz"
}
```

- [ ] **Step 2: Create `extension.js` skeleton**

```javascript
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';

export default class OpenshokzExtension extends Extension {
    enable() {}
    disable() {}
}
```

- [ ] **Step 3: Install and verify extension loads**

```bash
mkdir -p ~/.local/share/gnome-shell/extensions/openshokz@jfenal.github.com
cp -r gnome-extension/* ~/.local/share/gnome-shell/extensions/openshokz@jfenal.github.com/
gnome-extensions enable openshokz@jfenal.github.com
# Alt+F2 → r → Enter to restart Shell, or log out/in
gnome-extensions info openshokz@jfenal.github.com
```

Expected: `State: ENABLED`

- [ ] **Step 4: Commit**

```bash
git add gnome-extension/
git commit -m "feat: GNOME extension scaffold"
```

---

### Task 2: Subprocess helper and battery fetch

**Files:**
- Create: `gnome-extension/subprocess.js` — async subprocess wrapper
- Modify: `gnome-extension/extension.js` — import and test helper

**Interfaces:**
- Produces:
  - `runAsync(argv: string[]) -> Promise<{ok: boolean, stdout: string}>` — wraps `Gio.Subprocess` with `communicate_async`
  - `fetchBattery() -> Promise<string>` — runs `openshokz info --short`, parses battery line, returns e.g. `"40%"` or `"--"` on failure

- [ ] **Step 1: Implement `subprocess.js`**

`runAsync(argv)`:
```javascript
export async function runAsync(argv) {
    const proc = Gio.Subprocess.new(argv,
        Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_SILENCE);
    const [, stdout] = await proc.communicate_async(null, null);
    const ok = proc.get_exit_status() === 0;
    return {ok, stdout: stdout ? new TextDecoder().decode(stdout.get_data()) : ''};
}
```

`fetchBattery()`: call `runAsync(['openshokz', 'info', '--short'])`, find line matching `Battery:`, extract percentage. Return `'--'` on failure.

- [ ] **Step 2: Manual smoke test**

In `enable()`, call `fetchBattery().then(b => log('battery: ' + b))`. Enable extension, check `journalctl -f -o cat /usr/bin/gnome-shell` for the log line.

- [ ] **Step 3: Commit**

```bash
git add gnome-extension/subprocess.js gnome-extension/extension.js
git commit -m "feat: async subprocess helper and battery fetch"
```

---

### Task 3: Status indicator in top bar

**Files:**
- Create: `gnome-extension/indicator.js` — `OpenshokzIndicator extends SystemIndicator`
- Modify: `gnome-extension/extension.js` — create indicator in `enable()`, destroy in `disable()`

**Interfaces:**
- Consumes: `fetchBattery()` from Task 2
- Produces: `OpenshokzIndicator` — shows `🎧 NN%` in top bar; `updateBattery(text)` method; starts 300 s poll in constructor, cancels in `destroy()`

- [ ] **Step 1: Implement `indicator.js`**

```javascript
import {SystemIndicator} from 'resource:///org/gnome/shell/ui/quickSettings.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

export class OpenshokzIndicator extends SystemIndicator {
    constructor() {
        super();
        this._label = this._addIndicator();
        // St.Label — set text to '🎧 --'
        this._startPolling();
    }
    updateBattery(text) { this._label.text = `🎧 ${text}`; }
    _startPolling() { /* GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 300, ...) */ }
    destroy() { /* cancel timeout */ super.destroy(); }
}
```

Wire into `extension.js`: `enable()` → check `GLib.find_program_in_path('openshokz')`; if null, return. Create `OpenshokzIndicator`, add to `Main.panel.statusArea`.

- [ ] **Step 2: Visual verification**

Enable extension, restart Shell. Expected: `🎧 --` (or `🎧 40%`) visible in top bar.

- [ ] **Step 3: Commit**

```bash
git add gnome-extension/indicator.js gnome-extension/extension.js
git commit -m "feat: status indicator in top bar with battery"
```

---

### Task 4: Popup with EQ presets

**Files:**
- Create: `gnome-extension/presetMenu.js` — `OpenshokzMenu extends QuickSettingsMenu`
- Modify: `gnome-extension/indicator.js` — attach menu, wire clicks

**Interfaces:**
- Consumes: `runAsync(['openshokz', 'eq', 'list', '--json'])`, state file at `~/.config/openshokz/state.json`
- Produces: popup with one button per preset; active preset highlighted; click applies preset

- [ ] **Step 1: Implement `presetMenu.js`**

`OpenshokzMenu` extends `QuickSettingsMenu`. On open (`open()` override):
1. Call `runAsync(['openshokz', 'eq', 'list', '--json'])`, parse JSON
2. Read `~/.config/openshokz/state.json` (via `Gio.File` + `load_contents`) for active preset
3. Clear and rebuild button list: one `St.Button` per preset, active one styled with accent class

Button click: call `runAsync(['openshokz', 'eq', preset.arg])`, on success update active styling.

Header row: model name + battery (reuse cached battery text). "Not connected" label if last battery fetch failed.

"Open Settings →" button: `GLib.spawn_command_line_async('openshokz-app')` if found, else open terminal.

- [ ] **Step 2: Wire state file monitor**

```javascript
const stateFile = Gio.File.new_for_path(
    GLib.get_home_dir() + '/.config/openshokz/state.json');
this._monitor = stateFile.monitor_file(Gio.FileMonitorFlags.NONE, null);
this._monitor.connect('changed', () => this._refreshActivePreset());
```

- [ ] **Step 3: Visual and functional test**

1. Click indicator → popup appears with all presets
2. Click a preset → headset announces mode, button highlights
3. Headset disconnected → buttons insensitive, "Not connected" shown
4. Edit a preset in the CLI → popup shows updated name on next open

- [ ] **Step 4: Commit**

```bash
git add gnome-extension/presetMenu.js gnome-extension/indicator.js
git commit -m "feat: EQ preset popup with active state and file monitor"
```

---

### Task 5: Package and install script

**Files:**
- Create: `gnome-extension/install.sh` — copies extension to `~/.local/share/gnome-shell/extensions/`
- Modify: `README.md` — add GNOME extension install instructions
- Modify: `.gitignore` — add `gnome-extension/.eslintcache`

**Interfaces:**
- Produces: `make install-extension` or `bash gnome-extension/install.sh` → extension installed and enabled

- [ ] **Step 1: Write `install.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail
UUID="openshokz@jfenal.github.com"
DEST="$HOME/.local/share/gnome-shell/extensions/$UUID"
mkdir -p "$DEST"
cp -r "$(dirname "$0")"/* "$DEST/"
gnome-extensions enable "$UUID" 2>/dev/null || true
echo "Installed. Restart GNOME Shell (Alt+F2 → r) to activate."
```

- [ ] **Step 2: Update README**

Add section "GNOME Shell Extension" with install steps: run `bash gnome-extension/install.sh`, restart Shell, enable via Extensions app.

- [ ] **Step 3: Commit and push**

```bash
git add gnome-extension/install.sh README.md .gitignore
git commit -m "feat: extension install script and README instructions"
git push
```
