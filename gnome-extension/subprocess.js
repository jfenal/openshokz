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
    const [stdout] = await proc.communicate_async(null, null);
    const ok = proc.get_if_exited() && proc.get_exit_status() === 0;
    return {
        ok,
        stdout: stdout ? new TextDecoder().decode(stdout.get_data()) : '',
    };
}

