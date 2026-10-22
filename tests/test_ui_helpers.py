"""Tests for ui/headset.py subprocess helpers (no GTK required)."""

import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ui.headset import check_connected, run_openshokz


def _make_result(
    returncode: int, stdout: str = "", stderr: str = ""
) -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr=stderr)


class TestRunOpenshokz:
    def test_success_returns_true_and_stdout(self) -> None:
        with patch("subprocess.run", return_value=_make_result(0, '[{"name":"Standard"}]')):
            ok, out = run_openshokz("eq", "list", "--json")
        assert ok is True
        assert "Standard" in out

    def test_failure_returns_false(self) -> None:
        with patch("subprocess.run", return_value=_make_result(1, "", "error")):
            ok, _out = run_openshokz("eq", "standard")
        assert ok is False

    def test_spawn_error_returns_false(self) -> None:
        with patch("subprocess.run", side_effect=Exception("no binary")):
            ok, out = run_openshokz("eq", "list", "--json")
        assert ok is False
        assert "no binary" in out


class TestCheckConnected:
    def test_connected_when_exit_zero(self) -> None:
        with patch("ui.headset.run_openshokz", return_value=(True, "Firmware: HC")):
            assert check_connected() is True

    def test_not_connected_when_exit_nonzero(self) -> None:
        with patch("ui.headset.run_openshokz", return_value=(False, "")):
            assert check_connected() is False
