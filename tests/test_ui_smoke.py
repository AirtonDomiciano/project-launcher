from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import QApplication
except ImportError as exc:  # pragma: no cover
    QApplication = None
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None

from moah_launcher.actions import LauncherActions
from moah_launcher.ui.main_window import MainWindow
from moah_launcher.ui.theme import apply_theme


class RecordingRunner:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def open_directory(self, path: str) -> dict:
        self.calls.append(path)
        return {"ok": True, "path": path, "pid": 90 + len(self.calls), "error": None}


def _wait_until(predicate, timeout_ms: int = 4000) -> bool:
    elapsed = 0
    while elapsed < timeout_ms:
        QApplication.processEvents()
        if predicate():
            return True
        QTest.qWait(20)
        elapsed += 20
    return predicate()


@unittest.skipIf(QApplication is None, f"PyQt6 indisponível: {_IMPORT_ERROR}")
class UiSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        try:
            cls.app = QApplication.instance() or QApplication([])
        except Exception as exc:
            raise unittest.SkipTest(f"plataforma gráfica indisponível: {exc}") from exc
        cls.app.setQuitOnLastWindowClosed(False)
        apply_theme(cls.app)

    def tearDown(self) -> None:
        for widget in QApplication.topLevelWidgets():
            widget.close()
        QApplication.processEvents()

    def _actions(self, root: Path, projects: Path) -> tuple[LauncherActions, RecordingRunner]:
        runner = RecordingRunner()
        actions = LauncherActions(
            config_home=root / "config",
            data_home=root / "data",
            projects_root=str(projects),
            runner=runner,
        )
        return actions, runner

    def test_search_arrows_enter_and_favorite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            projects = root / "projetos"
            alpha = projects / "Alpha"
            beta = projects / "Beta"
            alpha.mkdir(parents=True)
            beta.mkdir()
            actions, runner = self._actions(root, projects)
            alpha_project = actions.add_manual_project(str(alpha))
            actions.add_manual_project(str(beta))
            window = MainWindow(actions, autodiscover=False)
            window.show()
            QTest.qWait(30)
            self.assertEqual(window.table.item(0, 1).text(), "Alpha")
            self.assertEqual(window.table.item(1, 1).text(), "Beta")

            QTest.keyClick(window.search, Qt.Key.Key_Down)
            QTest.keyClick(window.search, Qt.Key.Key_Return)
            self.assertEqual(runner.calls, [str(beta)])
            self.assertIn("Aberto no Cursor: Beta", window.status_label.text())
            self.assertEqual(actions.listProjects("recents")[0]["name"], "Beta")

            runner.calls.clear()
            QTest.keyClicks(window.search, "alpha")
            self.assertEqual(window.table.rowCount(), 1)
            self.assertEqual(window.table.item(0, 1).text(), "Alpha")
            QTest.keyClick(window.search, Qt.Key.Key_Return)
            self.assertEqual(runner.calls, [str(alpha)])

            window.search.clear()
            QTest.qWait(20)
            QTest.keyClick(window, Qt.Key.Key_D, Qt.KeyboardModifier.ControlModifier)
            favorites = actions.listProjects("favorites")
            self.assertTrue(favorites)
            self.assertEqual(favorites[0]["id"], actions.listProjects()[0]["id"])

            star = window.table.item(0, 0)
            self.assertEqual(star.text(), "★")
            rect = window.table.visualRect(window.table.model().index(0, 0))
            QTest.mouseClick(window.table.viewport(), Qt.MouseButton.LeftButton, pos=rect.center())
            self.assertEqual(actions.listProjects("favorites"), [])
            self.assertEqual(window.table.item(0, 0).text(), "☆")
            self.assertEqual(alpha_project["name"], "Alpha")

    def test_banner_for_missing_folder_and_ssd(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            projects = root / "projetos"
            (projects / "Aluai").mkdir(parents=True)
            actions, _runner = self._actions(root, projects)
            actions.set_source_roots([str(projects / "Aluai"), str(projects / "Sumiu")])
            window = MainWindow(actions, autodiscover=False)
            window.show()
            self.assertIn("Pasta indisponível", window.banner.text())
            self.assertIn("Sumiu", window.banner.text())
            self.assertNotIn("SSD indisponível", window.banner.text())

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            actions = LauncherActions(
                config_home=root / "config",
                data_home=root / "data",
                projects_root=str(root / "ssd-ausente"),
                runner=RecordingRunner(),
            )
            window = MainWindow(actions, autodiscover=False)
            window.show()
            self.assertIn("SSD indisponível", window.banner.text())

    def test_discovery_from_the_window_ignores_unselected_folders(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            projects = root / "projetos"
            app = projects / "Aluai" / "front"
            app.mkdir(parents=True)
            (app / "package.json").write_text("{}\n", encoding="utf-8")
            decoy = projects / "Outros" / "secret"
            decoy.mkdir(parents=True)
            (decoy / "package.json").write_text("{}\n", encoding="utf-8")
            actions, _runner = self._actions(root, projects)
            window = MainWindow(actions, autodiscover=True)
            window.show()
            self.assertTrue(_wait_until(lambda: window.completed_scans >= 1 and window.table.rowCount() >= 1))
            names = [window.table.item(row, 1).text() for row in range(window.table.rowCount())]
            categories = [window.table.item(row, 2).text() for row in range(window.table.rowCount())]
            self.assertIn("front", names)
            self.assertNotIn("secret", names)
            self.assertIn("Aluai", categories)
            self.assertTrue(window.discover_button.isEnabled())

    def test_group_opens_from_the_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            projects = root / "projetos"
            front = projects / "front"
            back = projects / "back"
            front.mkdir(parents=True)
            back.mkdir()
            actions, runner = self._actions(root, projects)
            front_project = actions.add_manual_project(str(front))
            back_project = actions.add_manual_project(str(back))
            actions.save_group("Aluai", [front_project["id"], back_project["id"]])
            window = MainWindow(actions, autodiscover=False)
            window.show()
            window.mode_buttons["groups"].click()
            QTest.qWait(20)
            self.assertEqual(window.table.item(0, 0).text(), "Aluai")
            QTest.keyClick(window.table, Qt.Key.Key_Return)
            self.assertEqual(runner.calls, [str(front), str(back)])
            self.assertIn("Grupo aberto no Cursor", window.status_label.text())
