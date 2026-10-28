"""Interface do launcher. Só conversa com LauncherActions."""

from __future__ import annotations

import os
import time

from PyQt6.QtCore import QEvent, QThread, QTimer, Qt
from PyQt6.QtGui import QColor, QFontDatabase, QKeySequence, QShortcut
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QButtonGroup,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QFileDialog,
)

from moah_launcher.actions import LauncherActions
from moah_launcher.messages import MANUAL_ONLY, NO_SOURCE_FOLDERS, folder_unavailable
from moah_launcher.ui.group_dialog import GroupDialog
from moah_launcher.ui.sources_dialog import SourcesDialog
from moah_launcher.ui.worker import DiscoverWorker


class MainWindow(QMainWindow):
    def __init__(self, actions: LauncherActions, autodiscover: bool = True) -> None:
        super().__init__()
        self.actions = actions
        self.autodiscover = autodiscover
        self.mode = "all"
        self._scan_token = 0
        self._worker: DiscoverWorker | None = None
        self._thread: QThread | None = None
        self._scan_warnings: list[str] = []
        self._last_open_id: str | None = None
        self._last_open_at = 0.0
        self.completed_scans = 0
        self.setWindowTitle("MOAH Project Launcher")
        self.setMinimumSize(780, 480)
        self._build()
        self._restore_size()
        self.refresh()
        QTimer.singleShot(0, self.search.setFocus)
        if autodiscover:
            QTimer.singleShot(0, self.discover)

    def _build(self) -> None:
        central = QWidget()
        layout = QVBoxLayout(central)
        layout.setContentsMargins(12, 10, 12, 8)
        layout.setSpacing(8)

        title = QLabel("MOAH Project Launcher")
        title.setObjectName("title")
        layout.addWidget(title)

        self.search = QLineEdit()
        self.search.setObjectName("search")
        self.search.setPlaceholderText("Buscar por nome, categoria ou caminho")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(lambda _text: self.refresh())
        self.search.installEventFilter(self)
        layout.addWidget(self.search)

        self.banner = QLabel()
        self.banner.setObjectName("banner")
        self.banner.setWordWrap(True)
        self.banner.hide()
        layout.addWidget(self.banner)

        modes = QHBoxLayout()
        self.mode_group = QButtonGroup(self)
        self.mode_group.setExclusive(True)
        self.mode_buttons: dict[str, QPushButton] = {}
        for mode, label in (
            ("all", "Todos"),
            ("favorites", "Favoritos"),
            ("recents", "Recentes"),
            ("groups", "Grupos"),
        ):
            button = QPushButton(label)
            button.setCheckable(True)
            button.setProperty("mode", mode)
            self.mode_group.addButton(button)
            self.mode_buttons[mode] = button
            modes.addWidget(button)
        self.mode_buttons["all"].setChecked(True)
        self.mode_group.buttonClicked.connect(self._on_mode)
        hint = QLabel("↑↓ navegar · Enter ou clique abre")
        hint.setObjectName("hint")
        modes.addStretch(1)
        modes.addWidget(hint)
        layout.addLayout(modes)

        actions = QHBoxLayout()
        self.open_button = self._button("Abrir", "Abrir no Cursor (Enter)", self.open_current)
        self.favorite_button = self._button(
            "Favorito",
            "Marcar ou desmarcar o projeto selecionado (Ctrl+D)",
            self.toggle_favorite,
        )
        self.sources_button = self._button("Pastas", "Escolher pastas de origem", self.choose_sources)
        self.discover_button = self._button("Descobrir", "Varrer as pastas de origem", self.discover)
        self.add_button = self._button("Adicionar", "Adicionar um projeto manualmente", self.add_manual)
        self.group_button = self._button("Novo grupo", "Abrir vários projetos de uma vez", self.new_group)
        self.edit_group_button = self._button("Editar grupo", "Alterar o grupo selecionado", self.edit_group)
        self.remove_button = self._button("Remover", "Remover projeto manual ou grupo", self.remove_selected)
        for button in (
            self.open_button,
            self.favorite_button,
            self.sources_button,
            self.discover_button,
            self.add_button,
            self.group_button,
            self.edit_group_button,
            self.remove_button,
        ):
            actions.addWidget(button)
        actions.addStretch(1)
        layout.addLayout(actions)

        self.table = QTableWidget(0, 4)
        self.table.setObjectName("projects")
        self.table.setAlternatingRowColors(True)
        self.table.setShowGrid(False)
        self.table.setWordWrap(False)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setTextElideMode(Qt.TextElideMode.ElideMiddle)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(30)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.itemClicked.connect(self._on_item_clicked)
        self.table.itemSelectionChanged.connect(self._update_buttons)
        self.table.installEventFilter(self)
        self.path_font = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        self.path_font.setPointSize(9)

        self.empty = QLabel()
        self.empty.setObjectName("empty")
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty.setWordWrap(True)
        self.stack = QStackedWidget()
        self.stack.addWidget(self.table)
        self.stack.addWidget(self.empty)
        layout.addWidget(self.stack, stretch=1)

        self.setCentralWidget(central)
        status = QStatusBar()
        self.status_label = QLabel("Pronto")
        self.status_label.setObjectName("hint")
        status.addWidget(self.status_label, 1)
        self.setStatusBar(status)

        favorite_shortcut = QShortcut(QKeySequence("Ctrl+D"), self)
        favorite_shortcut.setContext(Qt.ShortcutContext.ApplicationShortcut)
        favorite_shortcut.activated.connect(self.toggle_favorite)
        find_shortcut = QShortcut(QKeySequence.StandardKey.Find, self)
        find_shortcut.activated.connect(self.search.setFocus)

    def _button(self, label: str, tip: str, slot) -> QPushButton:
        button = QPushButton(label)
        button.setToolTip(tip)
        button.clicked.connect(lambda _checked=False, slot=slot: slot())
        return button

    def eventFilter(self, watched, event) -> bool:
        if event.type() == QEvent.Type.KeyPress:
            key = event.key()
            if watched is self.search and key in (Qt.Key.Key_Down, Qt.Key.Key_Up):
                delta = 1 if key == Qt.Key.Key_Down else -1
                self._move_selection(delta)
                return True
            if watched is self.search and key == Qt.Key.Key_Escape and self.search.text():
                self.search.clear()
                return True
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and watched in (self.search, self.table):
                self.open_current()
                return True
            if watched is self.table and key == Qt.Key.Key_F and self.mode != "groups":
                self.toggle_favorite()
                return True
        return super().eventFilter(watched, event)

    def refresh(self, keep_selection: bool = False, prefer_id: str | None = None) -> None:
        target = prefer_id or (self.current_id() if keep_selection else None)
        query = self.search.text()
        self.table.setRowCount(0)
        if self.mode == "groups":
            rows = self.actions.search_groups(query)
            self._fill_groups(rows)
            message = self._empty_groups_message(query) if not rows else ""
        else:
            rows = self.actions.searchProjects(query, scope=self.mode)
            self._fill_projects(rows)
            message = self._empty_projects_message(query) if not rows else ""
        if rows:
            self.stack.setCurrentWidget(self.table)
            self._select_id(target)
        else:
            self.empty.setText(message)
            self.stack.setCurrentWidget(self.empty)
        self._show_banner()
        self._show_status()
        self._update_buttons()

    def discover(self) -> None:
        roots = self.actions.source_roots()
        self._scan_token += 1
        token = self._scan_token
        if self._worker is not None:
            self._worker.cancel()
        if not roots:
            report = self.actions.status_report()
            self._scan_warnings = [] if not report["ssdAvailable"] else [NO_SOURCE_FOLDERS]
            self.discover_button.setEnabled(True)
            self.discover_button.setText("Descobrir")
            self.completed_scans += 1
            self.refresh(keep_selection=True)
            return
        worker = DiscoverWorker(roots)
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.progress.connect(lambda text, token=token: self._on_progress(token, text))
        worker.finished.connect(lambda result, token=token: self._on_discovered(token, result))
        worker.finished.connect(thread.quit)
        self._worker = worker
        self._thread = thread
        self.discover_button.setEnabled(False)
        self.discover_button.setText("Descobrindo…")
        self.status_label.setText("Descobrindo projetos…")
        thread.start()

    def choose_sources(self) -> None:
        report = self.actions.status_report()
        dialog = SourcesDialog(
            report["projectsRoot"],
            report["cursorBin"],
            self.actions.suggested_roots(),
            self.actions.source_roots(),
            report["ssdAvailable"],
            self,
        )
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        outcome = self.actions.set_source_roots(dialog.checked_paths())
        if outcome["rejected"]:
            lines = [item["error"] for item in outcome["rejected"]]
            QMessageBox.warning(self, "Pastas de origem", "\n".join(lines))
        self.refresh(keep_selection=True)
        self.discover()

    def add_manual(self) -> None:
        report = self.actions.status_report()
        start = report["projectsRoot"] if os.path.isdir(report["projectsRoot"]) else os.path.expanduser("~")
        selected = QFileDialog.getExistingDirectory(
            self,
            "Adicionar projeto",
            start,
            QFileDialog.Option.DontUseNativeDialog | QFileDialog.Option.ShowDirsOnly,
        )
        if not selected:
            return
        try:
            project = self.actions.add_manual_project(selected)
        except ValueError as exc:
            QMessageBox.warning(self, "Pasta indisponível", str(exc))
            return
        self.refresh(prefer_id=project["id"])

    def toggle_favorite(self) -> None:
        self._toggle_id(self.current_id())

    def new_group(self) -> None:
        self._edit_group(None)

    def edit_group(self) -> None:
        group_id = self.current_id()
        if not group_id:
            return
        groups = [group for group in self.actions.list_groups() if group["id"] == group_id]
        if not groups:
            return
        self._edit_group(groups[0])

    def remove_selected(self) -> None:
        selected = self.current_id()
        if not selected:
            return
        if self.mode == "groups":
            answer = QMessageBox.question(self, "Remover grupo", "Remover este grupo?")
            if answer != QMessageBox.StandardButton.Yes:
                return
            try:
                self.actions.delete_group(selected)
            except KeyError:
                return
            self.refresh()
            return
        project = self._project_by_id(selected)
        if not project or project["source"] != "manual":
            QMessageBox.information(self, "Remover projeto", MANUAL_ONLY)
            return
        answer = QMessageBox.question(
            self,
            "Remover projeto",
            f"Remover {project['name']} do catálogo? A pasta não será apagada.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.actions.remove_manual_project(selected)
        except (KeyError, ValueError) as exc:
            QMessageBox.warning(self, "Remover projeto", str(exc))
            return
        self.refresh()

    def open_current(self) -> None:
        selected = self.current_id()
        if not selected:
            return
        now = time.monotonic()
        if selected == self._last_open_id and now - self._last_open_at < 0.6:
            return
        if self.mode == "groups":
            result = self.actions.openGroup(selected)
        else:
            result = self.actions.openProject(selected)
        if result["ok"]:
            self._last_open_id = selected
            self._last_open_at = now
            self.refresh(prefer_id=selected)
            if self.mode == "groups":
                self.status_label.setText(f"Grupo aberto no Cursor: {result['name']}")
            else:
                self.status_label.setText(f"Aberto no Cursor: {result['name']}")
            return
        lines = [result.get("error") or "Falha ao abrir"]
        for item in result.get("results") or []:
            if not item["ok"]:
                label = item.get("name") or item.get("projectId")
                lines.append(f"{label}: {item.get('error')}")
        QMessageBox.warning(self, "Não foi possível abrir", "\n".join(dict.fromkeys(lines)))
        self.refresh(prefer_id=selected)

    def current_id(self) -> str | None:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if item is None:
            return None
        value = item.data(Qt.ItemDataRole.UserRole)
        return value if isinstance(value, str) else None

    def closeEvent(self, event) -> None:
        self.actions.save_window_size(self.width(), self.height())
        self._scan_token += 1
        if self._worker is not None:
            self._worker.cancel()
        if self._thread is not None:
            self._thread.quit()
            self._thread.wait(2000)
        super().closeEvent(event)

    def _on_mode(self, button) -> None:
        self.mode = button.property("mode")
        self.refresh()

    def _on_item_clicked(self, item: QTableWidgetItem) -> None:
        project_id = item.data(Qt.ItemDataRole.UserRole)
        if self.mode != "groups" and item.column() == 0:
            self._toggle_id(project_id if isinstance(project_id, str) else None)
            return
        self.table.selectRow(item.row())
        self.open_current()

    def _toggle_id(self, project_id: str | None) -> None:
        if self.mode == "groups" or not project_id:
            return
        try:
            self.actions.toggle_favorite(project_id)
        except KeyError:
            return
        self.refresh(prefer_id=project_id)

    def _on_progress(self, token: int, text: str) -> None:
        if token != self._scan_token:
            return
        self.status_label.setText(text)

    def _on_discovered(self, token: int, result) -> None:
        if token != self._scan_token:
            return
        self.discover_button.setEnabled(True)
        self.discover_button.setText("Descobrir")
        self.completed_scans += 1
        if result.cancelled:
            self.status_label.setText("Descoberta cancelada")
            return
        self.actions.apply_discovery(result)
        self._scan_warnings = [
            warning
            for warning in result.warnings
            if not warning.startswith("Pasta indisponível:")
        ]
        self.refresh(keep_selection=True)
        self.status_label.setText(
            f"{len(result.projects)} projetos encontrados · {result.directories_visited} pastas lidas"
        )

    def _fill_projects(self, projects: list[dict]) -> None:
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["★", "Nome", "Categoria", "Caminho"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 42)
        self.table.setColumnWidth(1, 220)
        self.table.setRowCount(len(projects))
        for row, project in enumerate(projects):
            star = QTableWidgetItem("★" if project["favorite"] else "☆")
            star.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            star.setForeground(QColor("#e0af68" if project["favorite"] else "#6d7588"))
            name = QTableWidgetItem(project["name"])
            category = QTableWidgetItem(project["category"])
            path = QTableWidgetItem(project["path"])
            path.setFont(self.path_font)
            tip = project["path"]
            if project["source"] == "manual":
                tip += "\nAdicionado manualmente"
            if not project["available"]:
                tip += f"\n{folder_unavailable(project['path'])}"
            for item in (star, name, category, path):
                item.setData(Qt.ItemDataRole.UserRole, project["id"])
                item.setToolTip(tip)
                if not project["available"]:
                    item.setForeground(QColor("#8b93a7"))
            if project["favorite"] and project["available"]:
                star.setForeground(QColor("#e0af68"))
            self.table.setItem(row, 0, star)
            self.table.setItem(row, 1, name)
            self.table.setItem(row, 2, category)
            self.table.setItem(row, 3, path)

    def _fill_groups(self, groups: list[dict]) -> None:
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["Nome", "Projetos", "Caminhos"])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(0, 180)
        self.table.setRowCount(len(groups))
        for row, group in enumerate(groups):
            names = ", ".join(project["name"] for project in group["projects"]) or "—"
            paths = " · ".join(project["path"] for project in group["projects"] if project["path"])
            name_item = QTableWidgetItem(group["name"])
            projects_item = QTableWidgetItem(names)
            paths_item = QTableWidgetItem(paths)
            paths_item.setFont(self.path_font)
            for item in (name_item, projects_item, paths_item):
                item.setData(Qt.ItemDataRole.UserRole, group["id"])
                item.setToolTip(f"{group['name']}\n{names}\n{paths}")
            self.table.setItem(row, 0, name_item)
            self.table.setItem(row, 1, projects_item)
            self.table.setItem(row, 2, paths_item)

    def _select_id(self, project_id: str | None) -> None:
        if self.table.rowCount() == 0:
            return
        if project_id:
            for row in range(self.table.rowCount()):
                item = self.table.item(row, 0)
                if item and item.data(Qt.ItemDataRole.UserRole) == project_id:
                    self.table.selectRow(row)
                    return
        self.table.selectRow(0)

    def _move_selection(self, delta: int) -> None:
        count = self.table.rowCount()
        if count == 0:
            return
        keep_search = self.search.hasFocus()
        row = self.table.currentRow()
        if row < 0:
            row = 0
        else:
            row = max(0, min(count - 1, row + delta))
        self.table.selectRow(row)
        self.table.scrollToItem(self.table.item(row, 0))
        if keep_search:
            self.search.setFocus()

    def _show_banner(self) -> None:
        report = self.actions.status_report()
        lines = list(report["messages"])
        for warning in self._scan_warnings:
            if warning not in lines:
                lines.append(warning)
        if len(lines) > 4:
            extra = len(lines) - 3
            lines = lines[:3] + [f"e mais {extra} avisos"]
        if lines:
            self.banner.setText("\n".join(lines))
            self.banner.show()
        else:
            self.banner.hide()

    def _show_status(self) -> None:
        report = self.actions.status_report()
        if self.mode == "groups":
            listed = f"{self.table.rowCount()} grupos"
        else:
            listed = f"{self.table.rowCount()} nesta lista · {report['projectCount']} no catálogo"
        self.status_label.setText(f"{listed}  ·  ↑↓ navegar · Enter ou clique abre")

    def _update_buttons(self) -> None:
        has_row = self.table.rowCount() > 0 and self.table.currentRow() >= 0
        groups = self.mode == "groups"
        self.open_button.setEnabled(has_row)
        self.favorite_button.setEnabled(has_row and not groups)
        self.edit_group_button.setEnabled(has_row and groups)
        self.remove_button.setEnabled(self._can_remove())

    def _can_remove(self) -> bool:
        selected = self.current_id()
        if not selected:
            return False
        if self.mode == "groups":
            return True
        project = self._project_by_id(selected)
        return bool(project and project["source"] == "manual")

    def _empty_projects_message(self, query: str) -> str:
        if query.strip():
            return "Nenhum projeto encontrado."
        if self.mode == "favorites":
            return "Nenhum favorito ainda. Selecione um projeto e marque a estrela."
        if self.mode == "recents":
            return "Nenhum projeto recente. Abra um projeto para ele aparecer aqui."
        return "Nenhum projeto cadastrado. Escolha as pastas de origem ou adicione uma pasta."

    def _empty_groups_message(self, query: str) -> str:
        if query.strip():
            return "Nenhum grupo encontrado."
        return "Nenhum grupo. Crie um grupo para abrir vários projetos de uma vez."

    def _edit_group(self, group: dict | None) -> None:
        projects = self.actions.listProjects()
        if not projects:
            QMessageBox.information(
                self,
                "Novo grupo",
                "Cadastre ao menos um projeto antes de criar um grupo.",
            )
            return
        dialog = GroupDialog(projects, group, self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return
        name, project_ids = dialog.values()
        try:
            saved = self.actions.save_group(
                name,
                project_ids,
                group["id"] if group else None,
            )
        except ValueError as exc:
            QMessageBox.warning(self, "Grupo", str(exc))
            return
        self.mode = "groups"
        self.mode_buttons["groups"].setChecked(True)
        self.refresh(prefer_id=saved["id"])

    def _project_by_id(self, project_id: str) -> dict | None:
        for project in self.actions.listProjects():
            if project["id"] == project_id:
                return project
        return None

    def _restore_size(self) -> None:
        window = self.actions.status_report().get("window") or {}
        try:
            width = int(window.get("width") or 920)
            height = int(window.get("height") or 600)
        except (TypeError, ValueError, AttributeError):
            width, height = 920, 600
        self.resize(min(max(width, 780), 1600), min(max(height, 480), 1200))
