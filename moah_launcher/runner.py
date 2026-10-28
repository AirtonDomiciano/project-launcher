from __future__ import annotations

import os
import subprocess
import threading

from moah_launcher.constants import DEFAULT_CURSOR_BIN
from moah_launcher.messages import cursor_failed, cursor_missing, folder_unavailable
from moah_launcher.paths import normalize_path


class CursorRunner:
    """Inicia o Cursor com argv separado. Nunca passa por shell."""

    def __init__(self, binary: str = DEFAULT_CURSOR_BIN) -> None:
        self.binary = binary

    def open_directory(self, path: str) -> dict:
        try:
            normalized = normalize_path(path)
        except ValueError:
            return _failure(path, folder_unavailable(path))
        if not os.path.isdir(normalized):
            return _failure(normalized, folder_unavailable(normalized))
        if not os.path.exists(self.binary):
            return _failure(normalized, cursor_missing(self.binary))
        argv = [self.binary, "-n", normalized]
        try:
            process = subprocess.Popen(
                argv,
                shell=False,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
                close_fds=True,
            )
        except OSError as exc:
            return _failure(normalized, cursor_failed(str(exc)))
        _reap_in_background(process)
        return {"ok": True, "path": normalized, "pid": process.pid, "error": None}


def _failure(path: str, error: str) -> dict:
    return {"ok": False, "path": path, "pid": None, "error": error}


def _reap_in_background(process: subprocess.Popen) -> None:
    def wait_for_exit() -> None:
        try:
            process.wait()
        except OSError:
            return

    threading.Thread(target=wait_for_exit, name="cursor-reap", daemon=True).start()
