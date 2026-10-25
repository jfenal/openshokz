"""Tests for openshokz.ui.headset async wrapper (no GTK/hardware required)."""

import threading
import time
from unittest.mock import MagicMock, patch


class TestRunAsync:
    """run_async dispatches work to a background thread and calls back on GLib main loop."""

    def test_success_calls_callback_with_result(self) -> None:
        results: list[tuple[object, object]] = []

        mock_idle_add = MagicMock(side_effect=lambda cb, *args: cb(*args))

        with patch("openshokz.ui.headset.GLib") as mock_glib:
            mock_glib.idle_add = mock_idle_add
            from openshokz.ui.headset import run_async

            def _work() -> str:
                return "ok"

            def _callback(result: object, error: object) -> None:
                results.append((result, error))

            run_async(_callback, _work)
            # Give the thread time to complete
            time.sleep(0.1)

        assert len(results) == 1
        assert results[0] == ("ok", None)

    def test_exception_calls_callback_with_error(self) -> None:
        results: list[object] = []
        err = ValueError("boom")

        mock_idle_add = MagicMock(side_effect=lambda cb, *args: cb(*args))

        with patch("openshokz.ui.headset.GLib") as mock_glib:
            mock_glib.idle_add = mock_idle_add
            from openshokz.ui.headset import run_async

            def _fail() -> None:
                raise err

            def _callback(result: object, error: object) -> None:
                results.append((result, error))

            run_async(_callback, _fail)
            time.sleep(0.1)

        assert len(results) == 1
        result_tuple = results[0]
        assert isinstance(result_tuple, tuple)
        assert result_tuple[0] is None
        assert result_tuple[1] is err

    def test_runs_in_background_thread(self) -> None:
        thread_ids: list[int] = []

        mock_idle_add = MagicMock(side_effect=lambda cb, *args: cb(*args))

        with patch("openshokz.ui.headset.GLib") as mock_glib:
            mock_glib.idle_add = mock_idle_add
            from openshokz.ui.headset import run_async

            def _work() -> int:
                thread_ids.append(threading.get_ident())
                return 0

            run_async(lambda *_: None, _work)
            time.sleep(0.1)

        assert len(thread_ids) == 1
        assert thread_ids[0] != threading.main_thread().ident

    def test_passes_args_to_function(self) -> None:
        received: list[object] = []

        mock_idle_add = MagicMock(side_effect=lambda cb, *args: cb(*args))

        with patch("openshokz.ui.headset.GLib") as mock_glib:
            mock_glib.idle_add = mock_idle_add
            from openshokz.ui.headset import run_async

            def _work(a: int, b: str) -> tuple[int, str]:
                received.extend([a, b])
                return a, b

            run_async(lambda *_: None, _work, 42, "hello")
            time.sleep(0.1)

        assert received == [42, "hello"]
