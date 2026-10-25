import GObject from 'gi://GObject';
import {SystemIndicator} from 'resource:///org/gnome/shell/ui/quickSettings.js';

import {OpenshokzToggle} from './presetMenu.js';

export const OpenshokzIndicator = GObject.registerClass(
class OpenshokzIndicator extends SystemIndicator {
    _init() {
        super._init();
        this._indicatorIcon = this._addIndicator();
        this._indicatorIcon.icon_name = 'audio-headset-symbolic';

        this._toggle = new OpenshokzToggle();
        this.quickSettingsItems.push(this._toggle);
    }

    destroy() {
        if (this._toggle) {
            this._toggle.destroy();
            this._toggle = null;
        }
        super.destroy();
    }
});
