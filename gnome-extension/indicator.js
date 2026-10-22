import GLib from 'gi://GLib';
import St from 'gi://St';
import {SystemIndicator} from 'resource:///org/gnome/shell/ui/quickSettings.js';

import {fetchBattery} from './subprocess.js';

export class OpenshokzIndicator extends SystemIndicator {
    constructor() {
        super();
        this._indicatorLabel = this._addIndicator();
        this._indicatorLabel.text = '🎧 --';
        this._pollId = null;
        this._startPolling();
    }

    updateBattery(text) {
        this._indicatorLabel.text = `🎧 ${text}`;
    }

    _startPolling() {
        // Fetch immediately, then every 5 minutes
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
        super.destroy();
    }
}
