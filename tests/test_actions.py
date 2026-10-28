from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from moah_launcher.actions import LauncherActions
from moah_launcher.constants import SUGGESTED_ROOT_NAMES
from moah_launcher.discovery import discover_projects
from moah_launcher.ids import project_id_for_path
from moah_launcher.messages import (
    GROUP_NOT_FOUND,
    PROJECT_NOT_FOUND,
    folder_unavailable,
    ssd_unavailable,
)
from moah_launcher.paths import normalize_path


class RecordingRunner:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def open_directory(self, path: str) -> dict:
        self.calls.append(path)
        return {"ok": True, "path": path, "pid": 70 + len(self.calls), "error": None}


class ActionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.projetos = self.tmp / "projetos"
        self.aluai = self.projetos / "Aluai"
        self.front = self.aluai / "front"
        self.back = self.aluai / "back"
        self.front.mkdir(parents=True)
        self.back.mkdir(parents=True)
        (self.front / "package.json").write_text("{}\n", encoding="utf-8")
        (self.back / "pyproject.toml").write_text("[project]\nname='back'\n", encoding="utf-8")
        for name in (*SUGGESTED_ROOT_NAMES, "Outros", "Airton System"):
            (self.projetos / name).mkdir(exist_ok=True)
        self.runner = RecordingRunner()
        self.actions = LauncherActions(
            config_home=self.tmp / "config",
            data_home=self.tmp / "data",
            projects_root=str(self.projetos),
            runner=self.runner,
            max_recents=3,
        )

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_first_launch_selects_only_suggested_folders(self) -> None:
        names = [os.path.basename(path) for path in self.actions.source_roots()]
        self.assertEqual(list(names), list(SUGGESTED_ROOT_NAMES))
        self.assertNotIn("Outros", names)
        self.assertNotIn("Airton System", names)
        settings = self.tmp / "config" / "moah-project-launcher" / "settings.json"
        self.assertTrue(settings.exists())
        self.assertFalse(any(self.projetos.rglob("settings.json")))

    def test_search_open_and_recents(self) -> None:
        front = self.actions.add_manual_project(str(self.front))
        back = self.actions.add_manual_project(str(self.back))
        found = self.actions.searchProjects("front aluai")
        self.assertEqual([item["id"] for item in found], [front["id"]])
        self.assertEqual(self.actions.invoke("searchProjects", {"query": "back"}), [self.actions.searchProjects("back")[0]])

        opened = self.actions.openProject(front["id"])
        self.assertTrue(opened["ok"])
        self.assertEqual(self.runner.calls, [normalize_path(str(self.front))])
        self.assertEqual(self.actions.listProjects("recents")[0]["id"], front["id"])

        self.actions.openProject(back["id"])
        self.actions.openProject(front["id"])
        recents = [item["id"] for item in self.actions.listProjects("recents")]
        self.assertEqual(recents[0], front["id"])
        self.assertIn(back["id"], recents)

        self.runner.calls.clear()
        missing = self.actions.openProject("prj_nao_existe")
        self.assertFalse(missing["ok"])
        self.assertEqual(missing["error"], PROJECT_NOT_FOUND)
        self.assertEqual(self.runner.calls, [])

    def test_failed_open_does_not_record_recent(self) -> None:
        project = self.actions.add_manual_project(str(self.front))
        for child in self.front.iterdir():
            child.unlink()
        self.front.rmdir()
        from unittest.mock import patch

        with patch("moah_launcher.runner.subprocess.Popen") as popen:
            result = LauncherActions(
                config_home=self.tmp / "config",
                data_home=self.tmp / "data",
                projects_root=str(self.projetos),
            ).openProject(project["id"])
        popen.assert_not_called()
        self.assertFalse(result["ok"])
        self.assertIn("Pasta indisponível", result["error"])
        reloaded = LauncherActions(
            config_home=self.tmp / "config",
            data_home=self.tmp / "data",
            projects_root=str(self.projetos),
            runner=self.runner,
        )
        self.assertEqual(reloaded.listProjects("recents"), [])

    def test_group_opens_each_project_with_its_own_arguments(self) -> None:
        front = self.actions.add_manual_project(str(self.front))
        back = self.actions.add_manual_project(str(self.back))
        group = self.actions.save_group("Aluai", [front["id"], back["id"]])
        same = self.actions.save_group("Aluai front e back", [back["id"], front["id"]], group["id"])
        self.assertEqual(same["id"], group["id"])
        opened = self.actions.invoke("openGroup", {"groupId": group["id"]})
        self.assertTrue(opened["ok"])
        self.assertEqual(
            self.runner.calls,
            [normalize_path(str(self.back)), normalize_path(str(self.front))],
        )
        self.assertEqual(self.actions.listProjects("recents")[0]["id"], front["id"])
        unknown = self.actions.openGroup("grp_ausente")
        self.assertEqual(unknown["error"], GROUP_NOT_FOUND)

    def test_favorites_survive_rediscovery(self) -> None:
        discovered = discover_projects([str(self.aluai)])
        self.actions.apply_discovery(discovered)
        front = self.actions.searchProjects("front")[0]
        self.assertTrue(self.actions.toggle_favorite(front["id"]))
        self.assertEqual(front["id"], project_id_for_path(str(self.front)))
        for child in self.front.iterdir():
            child.unlink()
        self.front.rmdir()
        self.actions.apply_discovery(discover_projects([str(self.aluai)]))
        self.assertEqual(self.actions.listProjects("favorites"), [])
        self.front.mkdir()
        (self.front / "package.json").write_text("{}\n", encoding="utf-8")
        self.actions.apply_discovery(discover_projects([str(self.aluai)]))
        favorites = self.actions.listProjects("favorites")
        self.assertEqual([item["id"] for item in favorites], [front["id"]])

    def test_manual_project_is_kept_and_discovered_stale_entries_go_away(self) -> None:
        manual = self.tmp / "avulso"
        manual.mkdir()
        added = self.actions.add_manual_project(str(manual))
        self.assertEqual(added["category"], "Manual")
        self.assertEqual(added["source"], "manual")
        self.actions.apply_discovery(discover_projects(self.actions.source_roots()))
        again = self.actions.searchProjects("avulso")
        self.assertEqual(again[0]["source"], "manual")

        nested = self.aluai / "manual-app"
        nested.mkdir()
        manual_nested = self.actions.add_manual_project(str(nested))
        (nested / "package.json").write_text("{}\n", encoding="utf-8")
        self.actions.apply_discovery(discover_projects([str(self.aluai)]))
        kept = self.actions.searchProjects("manual-app")[0]
        self.assertEqual(kept["id"], manual_nested["id"])
        self.assertEqual(kept["source"], "manual")
        self.assertIn("package.json", kept["markers"])

        (self.back / "pyproject.toml").unlink()
        self.actions.apply_discovery(discover_projects([str(self.aluai)]))
        names = [item["name"] for item in self.actions.listProjects()]
        self.assertNotIn("back", names)
        self.assertIn("manual-app", names)
        self.assertIn("avulso", names)

    def test_unmounted_root_keeps_the_catalog_and_blocks_open(self) -> None:
        project = self.actions.add_manual_project(str(self.front))
        self.actions.apply_discovery(discover_projects([str(self.projetos / "IMEX")]))
        self.assertTrue(any(item["id"] == project["id"] for item in self.actions.listProjects()))
        os.rename(self.projetos, self.tmp / "desmontado")
        report = self.actions.status_report()
        self.assertFalse(report["ssdAvailable"])
        self.assertEqual(report["messages"][0], ssd_unavailable(self.actions.settings["projectsRoot"]))
        self.assertFalse(any(item.startswith("Pasta indisponível") for item in report["messages"]))
        listed = self.actions.listProjects()
        self.assertFalse(listed[0]["available"])
        from unittest.mock import patch

        fresh = LauncherActions(
            config_home=self.tmp / "config",
            data_home=self.tmp / "data",
            projects_root=str(self.projetos),
        )
        with patch("moah_launcher.runner.subprocess.Popen") as popen:
            opened = fresh.openProject(project["id"])
        popen.assert_not_called()
        self.assertEqual(opened["error"], folder_unavailable(project["path"]))

    def test_recent_list_is_capped(self) -> None:
        ids = []
        for index in range(4):
            path = self.tmp / f"extra-{index}"
            path.mkdir()
            ids.append(self.actions.add_manual_project(str(path))["id"])
            self.actions.openProject(ids[-1])
        recents = [item["id"] for item in self.actions.listProjects("recents")]
        self.assertEqual(len(recents), 3)
        self.assertNotIn(ids[0], recents)

    def test_source_roots_reject_filesystem_root_and_symlinks(self) -> None:
        real = self.tmp / "real"
        real.mkdir()
        link = self.tmp / "link"
        link.symlink_to(real, target_is_directory=True)
        missing = self.tmp / "ainda-nao"
        outcome = self.actions.set_source_roots(["/", str(link), str(missing), str(real)])
        self.assertEqual(
            outcome["saved"],
            [normalize_path(str(missing)), normalize_path(str(real))],
        )
        self.assertEqual(len(outcome["rejected"]), 2)

    def test_unknown_action_is_rejected(self) -> None:
        with self.assertRaises(KeyError):
            self.actions.invoke("launchShell", {"command": "cursor"})
