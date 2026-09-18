"""Cross-platform process and console helpers in scripts/common.py.

These are the pieces that made every deck and video command fail on Windows
(npm shims, lsof/ps, POSIX signals). The tests run the real helpers against
this interpreter and a short-lived child process so a regression shows up on
either platform.
"""

from __future__ import annotations

import contextlib
import importlib.util
import io
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "common.py"
SPEC = importlib.util.spec_from_file_location("officekit_common_platform", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
common = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = common
SPEC.loader.exec_module(common)


class ConsoleTests(unittest.TestCase):
    def test_configure_console_tolerates_redirected_streams(self) -> None:
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
            common.configure_console()
            print("→ —")
        self.assertEqual(buffer.getvalue(), "→ —\n")

    def test_configure_console_makes_real_streams_utf8(self) -> None:
        script = (
            "import importlib.util, sys; "
            f"spec = importlib.util.spec_from_file_location('c', {str(MODULE_PATH)!r}); "
            "m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); "
            "m.configure_console(); print('PASS x \\u2014 y \\u2192 z')"
        )
        env = dict(os.environ)
        env.pop("PYTHONIOENCODING", None)
        env.pop("PYTHONUTF8", None)
        result = subprocess.run(
            [sys.executable, "-X", "utf8=0", "-c", script],
            capture_output=True,
            env=env,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode("utf-8", "replace"))
        self.assertIn("PASS x — y → z".encode("utf-8"), result.stdout)


class NodeBinTests(unittest.TestCase):
    def test_node_bin_resolves_to_a_launchable_path(self) -> None:
        if shutil.which("npm") is None:
            self.skipTest("npm not installed")
        npm = common.node_bin("npm")
        self.assertTrue(Path(npm).is_file(), npm)
        if common.IS_WINDOWS:
            self.assertTrue(npm.lower().endswith((".cmd", ".exe", ".bat")), npm)
        result = subprocess.run([npm, "--version"], capture_output=True, text=True, check=False)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertRegex(result.stdout.strip(), r"^\d+\.\d+\.\d+")

    def test_node_bin_names_the_missing_tool(self) -> None:
        with self.assertRaises(common.ScaffoldError) as ctx:
            common.node_bin("definitely-not-a-node-tool-xyz")
        self.assertIn("definitely-not-a-node-tool-xyz", str(ctx.exception))


class ProcessTests(unittest.TestCase):
    def test_pid_alive_reports_this_interpreter_and_a_finished_child(self) -> None:
        self.assertTrue(common.pid_alive(os.getpid()))
        child = subprocess.Popen([sys.executable, "-c", "pass"])
        child.wait(timeout=30)
        self.assertFalse(common.pid_alive(child.pid))
        self.assertFalse(common.pid_alive(-1))
        self.assertFalse(common.pid_alive(0))

    def test_spawn_detached_then_kill_pids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log = Path(tmp) / "child.log"
            pid = common.spawn_detached(
                [sys.executable, "-c", "import time; print('up', flush=True); time.sleep(60)"],
                cwd=Path(tmp),
                log_path=log,
            )
            try:
                self.assertTrue(common.pid_alive(pid))
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline and "up" not in log.read_text(encoding="utf-8"):
                    time.sleep(0.05)
                self.assertIn("up", log.read_text(encoding="utf-8"))
            finally:
                common.kill_pids([pid])
            self.assertFalse(common.pid_alive(pid))

    def test_pids_listening_on_finds_this_process(self) -> None:
        if not common.IS_WINDOWS and shutil.which("lsof") is None:
            self.skipTest("lsof not installed")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            sock.listen(1)
            port = sock.getsockname()[1]
            self.assertIn(os.getpid(), common.pids_listening_on(port))
        self.assertNotIn(os.getpid(), common.pids_listening_on(port))

    def test_process_command_describes_this_interpreter(self) -> None:
        if not common.IS_WINDOWS and shutil.which("ps") is None:
            self.skipTest("ps not installed")
        command = common.process_command(os.getpid())
        self.assertIn(Path(sys.executable).stem.lower(), command.lower())

    def test_stop_pidfile_handles_dead_and_live_pids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            pidfile = Path(tmp) / "dev.pid"
            common.write_pidfile(pidfile, 2**22 + 12345, port=1, slug="x")
            notes = common.stop_pidfile(pidfile)
            self.assertTrue(any("already stopped" in note for note in notes), notes)
            self.assertFalse(pidfile.exists())

            pid = common.spawn_detached(
                [sys.executable, "-c", "import time; time.sleep(60)"],
                cwd=Path(tmp),
                log_path=Path(tmp) / "live.log",
            )
            common.write_pidfile(pidfile, pid, port=1, slug="x")
            notes = common.stop_pidfile(pidfile)
            self.assertTrue(any("stopped pid" in note for note in notes), notes)
            self.assertFalse(common.pid_alive(pid))


if __name__ == "__main__":
    unittest.main()
