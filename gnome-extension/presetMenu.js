import GLib from 'gi://GLib';
import Gio from 'gi://Gio';
import St from 'gi://St';
import Clutter from 'gi://Clutter';
import {QuickSettingsMenu} from 'resource:///org/gnome/shell/ui/quickSettings.js';

import {runAsync} from './subprocess.js';

const STATE_PATH = GLib.get_home_dir() + '/.config/openshokz/state.json';

function _readActivePreset() {
    try {
        const file = Gio.File.new_for_path(STATE_PATH);
        const [, contents] = file.load_contents(null);
        const state = JSON.parse(new TextDecoder().decode(contents));
        return state.active_eq ?? null;
    } catch (e) {
        // State file may not exist on first run — that's expected
        if (!e.message?.includes('No such file'))
            log(`openshokz: could not read state file: ${e.message}`);
        return null;
    }
}

export class OpenshokzMenu extends QuickSettingsMenu {
    constructor(indicator, batteryRef) {
        super(indicator, 1);
        this._batteryRef = batteryRef; // object with {text} updated by indicator
        this._activePreset = null;
        this._presetButtons = [];
        this._monitor = null;
        this._connected = false;

        this._buildHeader();
        this._buildPresetList();
        this._buildFooter();
        this._watchStateFile();
    }

    _buildHeader() {
        const box = new St.BoxLayout({
            vertical: false,
            style_class: 'quick-settings-item-header',
        });

        this._headerLabel = new St.Label({text: 'OpenComm2', style_class: 'subtitle'});
        this._batteryLabel = new St.Label({
            text: this._batteryRef?.text ?? '--',
            x_expand: true,
            x_align: Clutter.ActorAlign.END,
        });

        box.add_child(this._headerLabel);
        box.add_child(this._batteryLabel);
        this.actor.add_child(box);
    }

    _buildPresetList() {
        this._presetsBox = new St.BoxLayout({vertical: true, style_class: 'popup-sub-menu'});
        this._notConnectedLabel = new St.Label({
            text: 'Not connected',
            style_class: 'subtitle',
            visible: false,
        });
        this._presetsBox.add_child(this._notConnectedLabel);
        this.actor.add_child(this._presetsBox);
    }

    _buildFooter() {
        const settingsBtn = new St.Button({
            label: 'Open Settings →',
            style_class: 'button',
            x_expand: true,
        });
        settingsBtn.connect('clicked', () => {
            const appPath = GLib.find_program_in_path('openshokz-app');
            if (appPath)
                GLib.spawn_command_line_async(`${appPath}`);
            else
                GLib.spawn_command_line_async('bash -c "openshokz --help"');
            this.close();
        });
        this.actor.add_child(settingsBtn);
    }

    _watchStateFile() {
        try {
            const file = Gio.File.new_for_path(STATE_PATH);
            this._monitor = file.monitor_file(Gio.FileMonitorFlags.NONE, null);
            this._monitor.connect('changed', () => {
                this._activePreset = _readActivePreset();
                this._refreshActiveHighlight();
            });
        } catch (_e) {
            // State file not yet created — no monitor needed
        }
    }

    _refreshActiveHighlight() {
        for (const {btn, arg} of this._presetButtons) {
            if (arg === this._activePreset)
                btn.add_style_class_name('selected');
            else
                btn.remove_style_class_name('selected');
        }
    }

    open(...args) {
        super.open(...args);
        this._activePreset = _readActivePreset();
        this._batteryLabel.text = this._batteryRef?.text ?? '--';
        this._loadPresets();
    }

    _loadPresets() {
        runAsync(['openshokz', 'eq', 'list', '--json']).then(({ok, stdout}) => {
            if (!ok) {
                this._showNotConnected(true);
                return;
            }
            const presets = JSON.parse(stdout);
            this._rebuildPresetButtons(presets);
            this._showNotConnected(false);
        }).catch(e => {
            logError(e, 'openshokz preset list');
            this._showNotConnected(true);
        });
    }

    _showNotConnected(show) {
        this._notConnectedLabel.visible = show;
        for (const {btn} of this._presetButtons)
            btn.reactive = !show;
    }

    _rebuildPresetButtons(presets) {
        // Remove old buttons (keep notConnectedLabel)
        for (const {btn} of this._presetButtons)
            this._presetsBox.remove_child(btn);
        this._presetButtons = [];

        for (const preset of presets) {
            const btn = new St.Button({
                label: preset.name,
                style_class: 'button',
                x_expand: true,
                reactive: true,
            });
            if (preset.arg === this._activePreset)
                btn.add_style_class_name('selected');

            btn.connect('clicked', () => {
                runAsync(['openshokz', 'eq', preset.arg]).then(({ok}) => {
                    if (ok) {
                        this._activePreset = preset.arg;
                        this._refreshActiveHighlight();
                    }
                }).catch(e => logError(e, 'openshokz eq apply'));
            });

            this._presetsBox.add_child(btn);
            this._presetButtons.push({btn, arg: preset.arg});
        }
    }

    destroy() {
        if (this._monitor) {
            this._monitor.cancel();
            this._monitor = null;
        }
        super.destroy();
    }
}
