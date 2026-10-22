import Gio from 'gi://Gio';

/**
 * Run a command asynchronously.
 * @param {string[]} argv
 * @returns {Promise<{ok: boolean, stdout: string}>}
 */
export async function runAsync(argv) {
    const proc = Gio.Subprocess.new(
        argv,
        Gio.SubprocessFlags.STDOUT_PIPE | Gio.SubprocessFlags.STDERR_SILENCE
    );
    const [, stdout] = await proc.communicate_async(null, null);
    const ok = proc.get_exit_status() === 0;
    return {
        ok,
        stdout: stdout ? new TextDecoder().decode(stdout.get_data()) : '',
    };
}

/**
 * Fetch battery level from headset.
 * Parses "Battery  : N/9 (NN%)" line from `openshokz info`.
 * @returns {Promise<string>} e.g. "40%" or "--" on failure
 */
export async function fetchBattery() {
    try {
        const {ok, stdout} = await runAsync(['openshokz', 'info']);
        if (!ok)
            return '--';
        for (const line of stdout.split('\n')) {
            const m = line.match(/Battery\s*:\s*\d+\/\d+\s*\((\d+)%\)/);
            if (m)
                return `${m[1]}%`;
        }
        return '--';
    } catch (_e) {
        return '--';
    }
}
