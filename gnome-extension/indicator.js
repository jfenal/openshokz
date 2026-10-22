import GLib from 'gi://GLib';
import {SystemIndicator} from 'resource:///org/gnome/shell/ui/quickSettings.js';

import {fetchBattery} from './subprocess.js';
import {OpenshokzMenu} from './presetMenu.js';

export class OpenshokzIndicator extends SystemIndicator {
    constructor() {
        super();
        this._indicatorLabel = this._addIndicator();
        this._indicatorLabel.text = '🎧 --';
        this._pollId = null;

        // batteryRef is shared with the menu so it can show current battery text
        this._batteryRef = {text: '--'};
        this._menu = new OpenshokzMenu(this, this._batteryRef);
        this.quickSettingsItems.push(this._menu);

        this._startPolling();
    }

    updateBattery(text) {
        this._indicatorLabel.text = `🎧 ${text}`;
        this._batteryRef.text = text;
    }

    _startPolling() {
        fetchBattery().then(b => this.updateBattery(b)).catch(() => {});
        this._pollId = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 300, () => {
            fetchBattery().then(b => this.updateBattery(b)).catch(() => {});
            return GLib.SOURCE_CONTINUE;
        });
    }

    destroy() {
        if (this._pollId !== null) {
            GLib.source_remove(this._pollId);
            this._pollId = null;
        }
        if (this._menu) {
            this._menu.destroy();
            this._menu = null;
        }
        super.destroy();
    }
}
