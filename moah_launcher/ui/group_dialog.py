from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
)

from moah_launcher.messages import GROUP_NEEDS_NAME, GROUP_NEEDS_PROJECT


class GroupDialog(QDialog):
    def __init__(self, projects: list[dict], group: dict | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Editar grupo" if group else "Novo grupo")
        self.resize(560, 480)
        selected = set(group["projectIds"]) if group else set()
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Nome do grupo"))
        self.name = QLineEdit(group["name"] if group else "")
        self.name.setPlaceholderText("Ex.: Aluai front e back")
        layout.addWidget(self.name)
        layout.addWidget(QLabel("Projetos abertos juntos"))
        self.filter = QLineEdit()
        self.filter.setPlaceholderText("Filtrar projetos")
        self.filter.textChanged.connect(self._apply_filter)
        layout.addWidget(self.filter)
        self.list = QListWidget()
        for project in projects:
            item = QListWidgetItem(f"{project['name']}  ·  {project['category']}")
            item.setData(Qt.ItemDataRole.UserRole, project["id"])
            item.setToolTip(project["path"])
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            checked = project["id"] in selected
            item.setCheckState(Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked)
            self.list.addItem(item)
        layout.addWidget(self.list, stretch=1)
        self.error = QLabel("")
        self.error.setObjectName("banner")
        self.error.setWordWrap(True)
        self.error.hide()
        layout.addWidget(self.error)
        box = QDialogButtonBox()
        box.addButton("Salvar", QDialogButtonBox.ButtonRole.AcceptRole)
        box.addButton("Cancelar", QDialogButtonBox.ButtonRole.RejectRole)
        box.accepted.connect(self._accept)
        box.rejected.connect(self.reject)
        layout.addWidget(box)

    def values(self) -> tuple[str, list[str]]:
        return self.name.text().strip(), self.checked_ids()

    def checked_ids(self) -> list[str]:
        ids: list[str] = []
        for index in range(self.list.count()):
            item = self.list.item(index)
            if item.checkState() == Qt.CheckState.Checked:
                ids.append(item.data(Qt.ItemDataRole.UserRole))
        return ids

    def _accept(self) -> None:
        if not self.name.text().strip():
            self._show_error(GROUP_NEEDS_NAME)
            return
        if not self.checked_ids():
            self._show_error(GROUP_NEEDS_PROJECT)
            return
        self.accept()

    def _show_error(self, text: str) -> None:
        self.error.setText(text)
        self.error.show()

    def _apply_filter(self, text: str) -> None:
        tokens = text.casefold().split()
        for index in range(self.list.count()):
            item = self.list.item(index)
            haystack = item.text().casefold()
            item.setHidden(bool(tokens) and not all(token in haystack for token in tokens))
