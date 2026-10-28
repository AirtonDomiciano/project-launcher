from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from moah_launcher.actions import LauncherActions
from moah_launcher.constants import IGNORED_DIRS, SUGGESTED_ROOT_NAMES
from moah_launcher.discovery import discover_projects


class RecordingRunner:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def open_directory(self, path: str) -> dict:
        self.calls.append(path)
        return {"ok": True, "path": path, "pid": 80, "error": None}


@unittest.skipUnless(os.path.isdir("/media/projetos"), "SSD de projetos indisponível")
class HostDiscoveryTests(unittest.TestCase):
    def test_real_folders_stay_inside_the_selected_roots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runner = RecordingRunner()
            actions = LauncherActions(
                config_home=root / "config",
                data_home=root / "data",
                projects_root="/media/projetos",
                runner=runner,
            )
            self.assertTrue(str(actions.repo.config_dir).startswith(tmp))
            self.assertFalse(str(actions.repo.data_dir).startswith("/media/projetos"))
            roots = actions.source_roots()
            names = [os.path.basename(path) for path in roots]
            self.assertEqual(names, [name for name in SUGGESTED_ROOT_NAMES if os.path.isdir(f"/media/projetos/{name}")])
            for forbidden in ("outros", "Outros", "Airton System", "Financiamento Argo"):
                self.assertNotIn(forbidden, names)

            result = discover_projects(roots)
            actions.apply_discovery(result)
            projects = actions.listProjects()
            self.assertGreater(len(projects), 0)
            ids = [project["id"] for project in projects]
            self.assertEqual(len(ids), len(set(ids)))
            forbidden_prefixes = (
                "/media/projetos/outros",
                "/media/projetos/Outros",
                "/media/projetos/Airton System",
                "/media/projetos/Financiamento Argo",
                "/media/projetos/$RECYCLE.BIN",
                "/media/projetos/System Volume Information",
            )
            for project in projects:
                self.assertTrue(
                    any(project["path"] == source or project["path"].startswith(source + os.sep) for source in roots),
                    project["path"],
                )
                self.assertTrue(set(Path(project["path"]).parts).isdisjoint(IGNORED_DIRS))
                for prefix in forbidden_prefixes:
                    self.assertFalse(project["path"].startswith(prefix), project["path"])

            moah = [project for project in projects if project["category"] == "MOAH" and project["name"] == "project-launcher"]
            self.assertTrue(moah, "o próprio launcher deveria ser encontrado em MOAH")
            available = next(project for project in projects if project["available"])
            opened = actions.openProject(available["id"])
            self.assertTrue(opened["ok"])
            self.assertEqual(runner.calls, [available["path"]])
            self.assertEqual(actions.listProjects("recents")[0]["id"], available["id"])
            self.assertNotEqual(runner.calls[0], "")
            self.assertNotIn("/usr/bin/cursor", runner.calls)
