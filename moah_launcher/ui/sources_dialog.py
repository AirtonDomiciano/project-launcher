from __future__ import annotations

import os

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from moah_launcher.messages import FILESYSTEM_ROOT_REJECTED, symlink_skipped
from moah_launcher.paths import normalize_path


class SourcesDialog(QDialog):
    def __init__(
        self,
        projects_root: str,
        cursor_bin: str,
        suggested: list[str],
        current: list[str],
        ssd_available: bool,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.projects_root = projects_root
        self.suggested = set(suggested)
        self.setWindowTitle("Pastas de origem")
        self.resize(640, 480)
        layout = QVBoxLayout(self)
        intro = QLabel(
            "Somente as pastas marcadas são varridas. "
            f"Nenhuma outra pasta de {projects_root} entra na descoberta "
            "até você adicioná-la aqui."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)
        meta = QLabel(f"Raiz: {projects_root}\nCursor: {cursor_bin}")
        meta.setObjectName("hint")
        layout.addWidget(meta)
        if not ssd_available:
            banner = QLabel(f"SSD indisponível: {projects_root} não está acessível.")
            banner.setObjectName("banner")
            banner.setWordWrap(True)
            layout.addWidget(banner)
        self.list = QListWidget()
        layout.addWidget(self.list, stretch=1)
        seen: list[str] = []
        for path in [*suggested, *current]:
            if path not in seen:
                seen.append(path)
        current_set = set(current)
        for path in seen:
            self._add_item(path, checked=path in current_set)
        buttons = QHBoxLayout()
        add_button = QPushButton("Adicionar pasta")
        add_button.clicked.connect(self._add_folder)
        suggest_button = QPushButton("Marcar sugeridas")
        suggest_button.clicked.connect(self._check_suggested)
        buttons.addWidget(add_button)
        buttons.addWidget(suggest_button)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        box = QDialogButtonBox()
        box.addButton("Salvar", QDialogButtonBox.ButtonRole.AcceptRole)
        box.addButton("Cancelar", QDialogButtonBox.ButtonRole.RejectRole)
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        layout.addWidget(box)

    def checked_paths(self) -> list[str]:
        paths: list[str] = []
        for index in range(self.list.count()):
            item = self.list.item(index)
            if item.checkState() == Qt.CheckState.Checked:
                paths.append(item.data(Qt.ItemDataRole.UserRole))
        return paths

    def _add_item(self, path: str, checked: bool) -> None:
        for index in range(self.list.count()):
            if self.list.item(index).data(Qt.ItemDataRole.UserRole) == path:
                if checked:
                    self.list.item(index).setCheckState(Qt.CheckState.Checked)
                return
        notes = []
        if path in self.suggested:
            notes.append("sugerida")
        if os.path.islink(path):
            notes.append("link simbólico")
        elif not os.path.isdir(path):
            notes.append("indisponível")
        label = path if not notes else f"{path}  ·  {' · '.join(notes)}"
        item = QListWidgetItem(label)
        item.setData(Qt.ItemDataRole.UserRole, path)
        item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
        item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
        self.list.addItem(item)

    def _add_folder(self) -> None:
        selected = QFileDialog.getExistingDirectory(
            self,
            "Adicionar pasta de origem",
            self.projects_root if os.path.isdir(self.projects_root) else str(os.path.expanduser("~")),
            QFileDialog.Option.DontUseNativeDialog | QFileDialog.Option.ShowDirsOnly,
        )
        if not selected:
            return
        try:
            path = normalize_path(selected)
        except ValueError:
            return
        if path == os.path.abspath(os.sep):
            QMessageBox.warning(self, "Pasta de origem", FILESYSTEM_ROOT_REJECTED)
            return
        if os.path.islink(path):
            QMessageBox.warning(self, "Pasta de origem", symlink_skipped(path))
            return
        if not os.path.isdir(path):
            QMessageBox.warning(self, "Pasta de origem", f"Pasta indisponível: {path}")
            return
        self._add_item(path, checked=True)

    def _check_suggested(self) -> None:
        for path in sorted(self.suggested):
            self._add_item(path, checked=True)
        for index in range(self.list.count()):
            item = self.list.item(index)
            if item.data(Qt.ItemDataRole.UserRole) in self.suggested:
                item.setCheckState(Qt.CheckState.Checked)
