# openshokz — AI Agent Notes

## GNOME Extension Debugging

### Quick Settings architecture (GNOME 43+)

The `quickSettingsItems` array on a `SystemIndicator` must contain **tile widgets**
(`QuickToggle` / `QuickMenuToggle`), NOT a full `QuickSettingsMenu` (popup).
Pushing a `QuickSettingsMenu` into `quickSettingsItems` silently fails — the menu
is created but never enters the Clutter stage; symptom is the repeated journal warning:

```
st_widget_get_theme_node called on the widget [StWidget ("…")] which is not in the stage.
```

Correct pattern:
- `SystemIndicator` → icon in the QS indicator row (top panel)
- `QuickMenuToggle` in `quickSettingsItems` → tile in the QS grid
- `QuickMenuToggle.menu` (a `QuickToggleMenu`) → submenu with actions

Wire the indicator to the panel via:
```javascript
Main.panel.statusArea.quickSettings.addExternalIndicator(this._indicator);
```
NOT `Main.panel._rightBox.insert_child_at_index(...)`.

The indicator icon must use `_addIndicator()` (returns `St.Icon`) with `icon_name`
set to a symbolic icon name. Setting `.text` on `St.Icon` is a no-op; use
`St.Label` added to `this._indicators` instead.

### Checking logs

Filter the *current* gnome-shell PID to avoid noise from previous sessions:

```bash
pgrep -a gnome-shell          # get the PID
journalctl -b --no-pager _PID=<pid> | grep -i openshokz
```

### Looking Glass (built-in JS REPL)

Works on Wayland: press `Alt+F2`, type `lg`, press Enter. It is a **modal** window.

**GNOME 50 limitation**: the old `imports.*` CJS module system is gone and
`global.extensionManager` is `undefined` — Looking Glass cannot reach the
extension manager at all. Useful only for inspecting Clutter widget state via
`global.stage`, not for loading/reloading extensions.

### GJS module cache

`gnome-extensions disable` + `enable` does **not** flush the GJS module cache.
Old bytecode keeps running until the session restarts. Symptom: log warnings
reference widget names that no longer exist in source.

`ReloadExtension` via D-Bus is deprecated and broken on GNOME 50 — returns
"does not work".

**Best dev-cycle tool**: nested session + `reload.sh`.

Start the nested shell once (runs inside a window in your current session):
```bash
gnome-shell --devkit --wayland
```

After each code change, install files and restart the nested shell:
```bash
./gnome-extension/reload.sh   # copies files to real UUID dir
# close the nested shell window, reopen it
```

Fresh GJS process each time — no module cache, no UUID tricks needed.

On Wayland (GNOME 50) it is **not possible** to inject a new extension UUID into
a running session from a shell script. `gnome-extensions enable` and the D-Bus
`EnableExtension` method both reject UUIDs the Shell hasn't seen at startup.
[ExtensionReloader](https://codeberg.org/som/ExtensionReloader) by som works
around this by running inside the Shell process itself.

### Re-registering a deleted extension

When an extension is removed via the Extensions app, the running GNOME Shell
session removes it from its internal registry. Simply copying files back to
`~/.local/share/gnome-shell/extensions/<uuid>/` is not enough — `gnome-extensions enable`
will return "does not exist".

There is no "Install from File" in the Extensions app (GNOME 50), and
`gnome-extensions install --force <zip>` is unreliable for brand-new UUIDs after deletion.
A full log-out/log-in is the only clean recovery path.

### `GObject.registerClass()` base class errors

`QuickSettingsMenu` is a plain ES6 class (not a GObject). Wrapping a subclass
of it with `GObject.registerClass()` raises:

```
TypeError: GObject.registerClass() used with invalid base class (is QuickSettingsMenu)
```

Use a plain `export class Foo extends QuickSettingsMenu` — no `registerClass`.
