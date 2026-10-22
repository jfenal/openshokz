import GLib from 'gi://GLib';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

import {OpenshokzIndicator} from './indicator.js';

export default class OpenshokzExtension extends Extension {
    enable() {
        if (!GLib.find_program_in_path('openshokz')) {
            log('openshokz: CLI not found on PATH, extension inactive');
            return;
        }

        this._indicator = new OpenshokzIndicator();
        Main.panel.statusArea['openshokz'] = this._indicator;
        Main.panel._rightBox.insert_child_at_index(this._indicator, 0);
    }

    disable() {
        if (this._indicator) {
            this._indicator.destroy();
            this._indicator = null;
        }
    }
}
