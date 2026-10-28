from __future__ import annotations

from PyQt6.QtCore import QObject, pyqtSignal

from moah_launcher.discovery import discover_projects


class DiscoverWorker(QObject):
    progress = pyqtSignal(str)
    finished = pyqtSignal(object)

    def __init__(self, roots: list[str]) -> None:
        super().__init__()
        self._roots = roots
        self._cancelled = False

    def cancel(self) -> None:
        self._cancelled = True

    def run(self) -> None:
        result = discover_projects(
            self._roots,
            on_progress=self.progress.emit,
            should_cancel=lambda: self._cancelled,
        )
        self.finished.emit(result)
