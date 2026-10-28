from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from moah_launcher.paths import xdg_config_home, xdg_data_home
from moah_launcher.persistence import Repository


class PersistenceTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self.project = self.tmp / "projeto"
        self.project.mkdir()
        (self.project / "package.json").write_text("{}\n", encoding="utf-8")
        self.before = sorted(path.name for path in self.project.iterdir())
        self.repo = Repository(self.tmp / "config", self.tmp / "data")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_roundtrip_uses_xdg_directories(self) -> None:
        self.repo.save_settings(
            {
                "version": 1,
                "cursorBin": "/usr/bin/cursor",
                "projectsRoot": "/media/projetos",
                "sourceRoots": ["/media/projetos/Aluai"],
                "window": {"width": 900, "height": 500},
            }
        )
        self.repo.save_projects(
            [
                {
                    "id": "prj_abc",
                    "name": "front",
                    "path": str(self.project),
                    "category": "Aluai",
                    "source": "discovered",
                    "markers": ["package.json"],
                }
            ]
        )
        self.repo.save_favorites(["prj_abc"])
        self.repo.save_recents([{"projectId": "prj_abc", "openedAt": "2026-10-28T18:00:00+00:00"}])
        self.repo.save_groups(
            [{"id": "grp_abc", "name": "Aluai", "projectIds": ["prj_abc"]}]
        )

        again = Repository(self.tmp / "config", self.tmp / "data")
        settings = again.read_settings()
        assert settings is not None
        self.assertEqual(settings["sourceRoots"], ["/media/projetos/Aluai"])
        self.assertEqual(again.read_projects()[0]["name"], "front")
        self.assertEqual(again.read_favorites(), ["prj_abc"])
        self.assertEqual(again.read_recents()[0]["projectId"], "prj_abc")
        self.assertEqual(again.read_groups()[0]["name"], "Aluai")
        self.assertTrue(str(again.config_dir).startswith(str(self.tmp / "config")))
        self.assertTrue(str(again.data_dir).startswith(str(self.tmp / "data")))
        self.assertFalse(str(again.config_dir).startswith(str(self.project)))
        self.assertEqual(self.before, sorted(path.name for path in self.project.iterdir()))
        self.assertFalse(list(self.repo.data_dir.glob("*.tmp")))
        self.assertFalse(list(self.repo.config_dir.glob(".*.tmp")))

    def test_corrupt_catalog_is_preserved_and_not_rewritten_in_place(self) -> None:
        self.repo.save_projects([])
        self.repo.catalog_path.write_text("{", encoding="utf-8")
        again = Repository(self.tmp / "config", self.tmp / "data")
        self.assertEqual(again.read_projects(), [])
        self.assertTrue((self.repo.data_dir / "catalog.json.corrupt").exists())
        self.assertTrue(again.load_warnings)

    def test_empty_xdg_env_falls_back_to_home(self) -> None:
        with patch.dict(os.environ, {"XDG_CONFIG_HOME": "", "XDG_DATA_HOME": "  "}, clear=False):
            self.assertEqual(xdg_config_home(), Path.home() / ".config")
            self.assertEqual(xdg_data_home(), Path.home() / ".local" / "share")

    def test_files_are_utf8_json(self) -> None:
        self.repo.save_groups([{"id": "grp_1", "name": "Ações", "projectIds": []}])
        raw = self.repo.groups_path.read_text(encoding="utf-8")
        self.assertIn("Ações", raw)
        self.assertEqual(json.loads(raw)["groups"][0]["name"], "Ações")
