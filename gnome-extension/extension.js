import {Extension} from 'resource:///org/gnome/shell/extensions/extension.js';
import {fetchBattery} from './subprocess.js';

export default class OpenshokzExtension extends Extension {
    enable() {
        // Smoke-test: log battery on enable (visible in journalctl)
        fetchBattery().then(b => log(`openshokz: battery ${b}`)).catch(() => {});
    }

    disable() {}
}
