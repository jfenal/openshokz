import GLib from 'gi://GLib';
import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import * as Main from 'resource:///org/gnome/shell/ui/main.js';

import {OpenshokzIndicator} from './indicator.js';

export default class OpenshokzExtension extends Extension {
    enable() {
        // GNOME Shell on Wayland inherits a minimal PATH; ~/.local/bin (uv tool
        // install target) is typically absent. Prepend it so subprocess calls work.
        const localBin = `${GLib.get_home_dir()}/.local/bin`;
        const currentPath = GLib.getenv('PATH') ?? '/usr/bin:/bin';
        if (!currentPath.split(':').includes(localBin))
            GLib.setenv('PATH', `${localBin}:${currentPath}`, true);

        if (!GLib.find_program_in_path('openshokz')) {
            log('openshokz: CLI not found on PATH, extension inactive');
            return;
        }

        try {
            this._indicator = new OpenshokzIndicator();
            Main.panel.statusArea.quickSettings.addExternalIndicator(this._indicator);
        } catch (e) {
            logError(e, 'openshokz: failed to enable indicator');
            this._indicator = null;
        }
    }

    disable() {
        try {
            if (this._indicator) {
                this._indicator.destroy();
                this._indicator = null;
            }
        } catch (e) {
            logError(e, 'openshokz: failed to disable indicator');
            this._indicator = null;
        }
    }
}
