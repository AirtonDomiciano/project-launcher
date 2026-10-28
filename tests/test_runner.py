from __future__ import annotations

import json
import os
import stat
import tempfile
import textwrap
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from moah_launcher.constants import DEFAULT_CURSOR_BIN
from moah_launcher.messages import cursor_missing, folder_unavailable
from moah_launcher.paths import normalize_path
from moah_launcher.runner import CursorRunner


class CursorRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.project = self.tmp / "front"
        self.project.mkdir()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_missing_directory_does_not_start_a_process(self) -> None:
        missing = self.tmp / "ausente"
        with patch("moah_launcher.runner.subprocess.Popen") as popen:
            result = CursorRunner().open_directory(str(missing))
        popen.assert_not_called()
        self.assertFalse(result["ok"])
        self.assertEqual(result["error"], folder_unavailable(normalize_path(str(missing))))

    def test_missing_binary_does_not_use_the_shell(self) -> None:
        missing_bin = self.tmp / "cursor-ausente"
        with patch("moah_launcher.runner.subprocess.Popen") as popen:
            result = CursorRunner(str(missing_bin)).open_directory(str(self.project))
        popen.assert_not_called()
        self.assertEqual(result["error"], cursor_missing(str(missing_bin)))

    def test_argv_is_a_list_and_shell_is_disabled(self) -> None:
        with patch("moah_launcher.runner.subprocess.Popen") as popen:
            popen.return_value.pid = 424242
            result = CursorRunner().open_directory(str(self.project))
        argv, kwargs = popen.call_args.args[0], popen.call_args.kwargs
        self.assertEqual(argv, [DEFAULT_CURSOR_BIN, "-n", normalize_path(str(self.project))])
        self.assertIsInstance(argv, list)
        self.assertTrue(all(isinstance(part, str) for part in argv))
        self.assertIs(kwargs["shell"], False)
        self.assertNotIn("executable", kwargs)
        self.assertTrue(result["ok"])
        self.assertEqual(result["pid"], 424242)
        self.assertEqual(DEFAULT_CURSOR_BIN, "/usr/bin/cursor")

    def test_metacharacters_stay_in_one_argument(self) -> None:
        marker = "moah-sentinel-not-created"
        nasty = self.tmp / f"proj; touch {marker}"
        nasty.mkdir()
        log_path = self.tmp / "argv.log"
        binary = self.tmp / "fake-cursor"
        binary.write_text(
            textwrap.dedent(
                """\
                #!/usr/bin/env python3
                import json, os, sys
                with open(os.environ["CURSOR_ARGV_LOG"], "a", encoding="utf-8") as handle:
                    handle.write(json.dumps(sys.argv) + "\\n")
                    handle.flush()
                    os.fsync(handle.fileno())
                """
            ),
            encoding="utf-8",
        )
        binary.chmod(binary.stat().st_mode | stat.S_IEXEC)
        cwd_sentinel = Path.cwd() / marker
        tmp_sentinel = self.tmp / marker
        os.environ["CURSOR_ARGV_LOG"] = str(log_path)
        try:
            result = CursorRunner(str(binary)).open_directory(str(nasty))
            deadline = time.time() + 3
            while time.time() < deadline and not log_path.exists():
                time.sleep(0.02)
            self.assertTrue(result["ok"])
            self.assertTrue(log_path.exists(), "o processo falso não gravou os argumentos")
            argv = json.loads(log_path.read_text(encoding="utf-8").splitlines()[0])
            self.assertEqual(argv, [str(binary), "-n", normalize_path(str(nasty))])
            self.assertFalse(cwd_sentinel.exists())
            self.assertFalse(tmp_sentinel.exists())
            self.assertNotEqual(argv[0], "/bin/sh")
        finally:
            os.environ.pop("CURSOR_ARGV_LOG", None)
            for leftover in (cwd_sentinel, tmp_sentinel):
                if leftover.exists():
                    leftover.unlink()

    def test_package_never_opts_into_a_shell(self) -> None:
        root = Path(__file__).resolve().parents[1] / "moah_launcher"
        for path in root.rglob("*.py"):
            source = path.read_text(encoding="utf-8")
            self.assertNotIn("shell=True", source, path.name)
            self.assertNotIn("os.system", source, path.name)
            self.assertNotIn("shell=True", source)

    def test_installed_cursor_is_executable_but_not_launched(self) -> None:
        cursor = Path("/usr/bin/cursor")
        if not cursor.exists():
            self.skipTest("cursor ausente")
        self.assertTrue(os.access(cursor, os.X_OK))
        self.assertTrue(cursor.is_symlink() or cursor.is_file())
