import GLib from 'gi://GLib';
import GObject from 'gi://GObject';
import {SystemIndicator} from 'resource:///org/gnome/shell/ui/quickSettings.js';

import {fetchBattery} from './subprocess.js';
import {OpenshokzMenu} from './presetMenu.js';

export const OpenshokzIndicator = GObject.registerClass(
class OpenshokzIndicator extends SystemIndicator {
    _init() {
        super._init();
        this._indicatorLabel = this._addIndicator();
        this._indicatorLabel.text = '🎧 --';
        this._pollId = null;
        this._alive = true; // guard against callbacks after destroy()

        // batteryRef is shared with the menu so it can show current battery text
        this._batteryRef = {text: '--'};
        this._menu = new OpenshokzMenu(this, this._batteryRef);
        this.quickSettingsItems.push(this._menu);

        this._startPolling();
    }

    updateBattery(text) {
        if (!this._alive)
            return;
        this._indicatorLabel.text = `🎧 ${text}`;
        this._batteryRef.text = text;
    }

    _startPolling() {
        fetchBattery().then(b => this.updateBattery(b)).catch(e => logError(e, 'openshokz battery fetch'));
        this._pollId = GLib.timeout_add_seconds(GLib.PRIORITY_DEFAULT, 300, () => {
            fetchBattery().then(b => this.updateBattery(b)).catch(e => logError(e, 'openshokz battery poll'));
            return GLib.SOURCE_CONTINUE;
        });
    }

    destroy() {
        this._alive = false; // prevent in-flight async callbacks from touching destroyed widgets
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
});
