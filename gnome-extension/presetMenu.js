import GLib from 'gi://GLib';
import Gio from 'gi://Gio';
import GObject from 'gi://GObject';
import * as PopupMenu from 'resource:///org/gnome/shell/ui/popupMenu.js';
import {QuickMenuToggle} from 'resource:///org/gnome/shell/ui/quickSettings.js';

import {runAsync} from './subprocess.js';

const STATE_PATH = GLib.get_home_dir() + '/.config/openshokz/state.json';

function _readActivePreset() {
    try {
        const file = Gio.File.new_for_path(STATE_PATH);
        const [, contents] = file.load_contents(null);
        const state = JSON.parse(new TextDecoder().decode(contents));
        return state.active_eq ?? null;
    } catch (e) {
        if (!e.message?.includes('No such file'))
            log(`openshokz: could not read state file: ${e.message}`);
        return null;
    }
}

export const OpenshokzToggle = GObject.registerClass(
class OpenshokzToggle extends QuickMenuToggle {
    _init() {
        super._init({
            title: 'OpenShokz',
        });
        this.iconName = 'audio-headset-symbolic';

        this._activePreset = _readActivePreset();
        this._presetItems = [];
        this._monitor = null;
        this._loading = false;
        this._retryId = null;

        this._notConnectedItem = new PopupMenu.PopupMenuItem('Not connected', {reactive: false});
        this.menu.addMenuItem(this._notConnectedItem);

        this._presetsSection = new PopupMenu.PopupMenuSection();
        this.menu.addMenuItem(this._presetsSection);

        this.menu.addAction('Open Settings →', () => {
            const appPath = GLib.find_program_in_path('openshokz-app');
            if (appPath)
                GLib.spawn_command_line_async(appPath);
            else
                GLib.spawn_command_line_async('bash -c "openshokz --help"');
            this.menu.close();
        });

        this.menu.connect('open-state-changed', (_menu, open) => {
            if (open)
                this._loadPresets();
        });

        this._watchStateFile();
        this._loadPresets();
    }

    _watchStateFile() {
        try {
            Gio.File.new_for_path(GLib.path_get_dirname(STATE_PATH))
                .make_directory_with_parents(null);
        } catch (_e) {
            // already exists
        }
        try {
            const file = Gio.File.new_for_path(STATE_PATH);
            this._monitor = file.monitor_file(Gio.FileMonitorFlags.NONE, null);
            this._monitor.connect('changed', () => {
                this._activePreset = _readActivePreset();
                this._refreshActiveHighlight();
            });
        } catch (e) {
            log(`openshokz: could not watch state file: ${e.message}`);
        }
    }

    _refreshActiveHighlight() {
        for (const {item, arg, label} of this._presetItems) {
            item.setOrnament(arg === this._activePreset
                ? PopupMenu.Ornament.DOT
                : PopupMenu.Ornament.NO_DOT);
            if (arg === this._activePreset)
                this.subtitle = label;
        }
    }

    _loadPresets() {
        if (this._loading)
            return;
        this._loading = true;
        runAsync(['openshokz', 'eq', 'list']).then(({ok, stdout}) => {
            this._loading = false;
            if (!ok) {
                this._showNotConnected(true);
                this._scheduleRetry();
                return;
            }
            this._cancelRetry();
            const presets = JSON.parse(stdout);
            this._rebuildPresetItems(presets);
            this._showNotConnected(false);
        }).catch(e => {
            this._loading = false;
            logError(e, 'openshokz preset list');
            this._showNotConnected(true);
            this._scheduleRetry();
        });
    }

    _scheduleRetry() {
        if (this._retryId !== null)
            return;
        this._retryId = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 30, () => {
            this._retryId = null;
            this._loadPresets();
            return GLib.SOURCE_REMOVE;
        });
    }

    _cancelRetry() {
        if (this._retryId !== null) {
            GLib.source_remove(this._retryId);
            this._retryId = null;
        }
    }

    _showNotConnected(show) {
        this._notConnectedItem.visible = show;
        for (const {item} of this._presetItems)
            item.reactive = !show;
    }

    _rebuildPresetItems(presets) {
        this._presetsSection.removeAll();
        this._presetItems = [];

        for (const preset of presets) {
            const item = new PopupMenu.PopupMenuItem(preset.name);
            item.setOrnament(preset.arg === this._activePreset
                ? PopupMenu.Ornament.DOT
                : PopupMenu.Ornament.NO_DOT);

            item.connect('activate', () => {
                runAsync(['openshokz', 'eq', preset.arg]).then(({ok}) => {
                    if (ok) {
                        this._activePreset = preset.arg;
                        this._refreshActiveHighlight();
                    }
                }).catch(e => logError(e, 'openshokz eq apply'));
            });

            this._presetsSection.addMenuItem(item);
            this._presetItems.push({item, arg: preset.arg, label: preset.name});
        }

        if (this._presetItems.length > 0)
            this._refreshActiveHighlight();
    }

    destroy() {
        this._cancelRetry();
        if (this._monitor) {
            this._monitor.cancel();
            this._monitor = null;
        }
        super.destroy();
    }
});
