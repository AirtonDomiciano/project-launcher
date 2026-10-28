from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from moah_launcher.constants import IGNORED_DIRS, MARKER_NAMES
from moah_launcher.discovery import discover_projects
from moah_launcher.ids import project_id_for_path
from moah_launcher.messages import folder_unavailable, no_permission, symlink_skipped
from moah_launcher.paths import normalize_path


class DiscoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.projetos = self.root / "projetos"
        self.aluai = self.projetos / "Aluai"
        self.aluai.mkdir(parents=True)
        self.outros = self.projetos / "Outros"
        self.outros.mkdir()

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_markers_ignores_symlinks_and_unselected_roots(self) -> None:
        app = self.aluai / "front"
        app.mkdir()
        (app / "package.json").write_text("{}", encoding="utf-8")
        (app / ".git").mkdir()
        (app / ".git" / "package.json").write_text("{}", encoding="utf-8")

        worktree = self.aluai / "worktree"
        worktree.mkdir()
        (worktree / ".git").write_text("gitdir: /somewhere\n", encoding="utf-8")

        service = self.aluai / "api"
        service.mkdir()
        (service / "pyproject.toml").write_text("[project]\nname='api'\n", encoding="utf-8")

        cli = self.aluai / "cli"
        cli.mkdir()
        (cli / "Cargo.toml").write_text("[package]\nname='cli'\n", encoding="utf-8")

        worker = self.aluai / "worker"
        worker.mkdir()
        (worker / "go.mod").write_text("module example.com/worker\n", encoding="utf-8")

        notes = self.aluai / "notes"
        notes.mkdir()
        (notes / "README.md").write_text("sem marcador\n", encoding="utf-8")

        for ignored in IGNORED_DIRS:
            if ignored == ".git":
                continue
            hidden = app / ignored / "dep"
            hidden.mkdir(parents=True)
            marker = "Cargo.toml" if ignored == "vendor" else "package.json"
            (hidden / marker).write_text("{}", encoding="utf-8")

        linked = self.aluai / "front-link"
        linked.symlink_to(app, target_is_directory=True)
        (self.aluai / "loop").symlink_to(self.aluai, target_is_directory=True)

        decoy = self.outros / "secret"
        decoy.mkdir()
        (decoy / "package.json").write_text("{}", encoding="utf-8")

        apps = self.aluai / "apps"
        front = apps / "front"
        front.mkdir(parents=True)
        (front / "package.json").write_text("{}", encoding="utf-8")
        other = self.aluai / "other"
        other.mkdir()
        (other / "go.mod").write_text("module example.com/other\n", encoding="utf-8")

        roots = [str(self.aluai), str(self.aluai), str(apps)]
        result = discover_projects(roots)
        paths = [project.path for project in result.projects]

        self.assertFalse(result.cancelled)
        self.assertEqual(len(paths), len(set(paths)))
        self.assertIn(str(app), paths)
        self.assertIn(str(worktree), paths)
        self.assertIn(str(service), paths)
        self.assertIn(str(cli), paths)
        self.assertIn(str(worker), paths)
        self.assertIn(str(front), paths)
        self.assertIn(str(other), paths)
        self.assertNotIn(str(notes), paths)
        self.assertNotIn(str(linked), paths)
        self.assertNotIn(str(decoy), paths)
        self.assertNotIn(str(app / ".git"), paths)

        by_path = {project.path: project for project in result.projects}
        self.assertEqual(by_path[str(app)].markers, (".git", "package.json"))
        self.assertEqual(by_path[str(worktree)].markers, (".git",))
        self.assertEqual(by_path[str(front)].category, "apps")
        self.assertEqual(by_path[str(other)].category, "Aluai")
        self.assertEqual(by_path[str(app)].name, "front")
        self.assertTrue(all(part not in IGNORED_DIRS for project in result.projects for part in Path(project.path).parts))
        self.assertTrue(str(apps) in result.scanned_roots)
        self.assertNotIn(str(self.outros), result.scanned_roots)

    def test_missing_root_and_symlink_root_are_not_scanned(self) -> None:
        missing = self.projetos / "IMEX"
        link = self.projetos / "Agents"
        target = self.root / "fora"
        target.mkdir()
        (target / "package.json").write_text("{}", encoding="utf-8")
        link.symlink_to(target, target_is_directory=True)

        result = discover_projects([str(missing), str(link), str(self.aluai)])
        self.assertEqual(result.missing_roots, (str(missing),))
        self.assertIn(folder_unavailable(str(missing)), result.warnings)
        self.assertIn(symlink_skipped(str(link)), result.warnings)
        self.assertEqual(result.projects, ())
        self.assertNotIn(str(target), [project.path for project in result.projects])

    def test_cancel_discards_partial_results(self) -> None:
        app = self.aluai / "front"
        app.mkdir()
        (app / "package.json").write_text("{}", encoding="utf-8")
        result = discover_projects([str(self.aluai)], should_cancel=lambda: True)
        self.assertTrue(result.cancelled)
        self.assertEqual(result.projects, ())
        self.assertEqual(result.scanned_roots, ())

    def test_unreadable_directory_does_not_abort(self) -> None:
        if os.geteuid() == 0:
            self.skipTest("root ignora chmod 000")
        locked = self.aluai / "locked"
        locked.mkdir()
        (locked / "package.json").write_text("{}", encoding="utf-8")
        visible = self.aluai / "visible"
        visible.mkdir()
        (visible / "package.json").write_text("{}", encoding="utf-8")
        locked.chmod(0)
        try:
            result = discover_projects([str(self.aluai)])
        finally:
            locked.chmod(0o755)
        paths = [project.path for project in result.projects]
        self.assertIn(str(visible), paths)
        self.assertNotIn(str(locked), paths)
        self.assertIn(no_permission(str(locked)), result.warnings)

    def test_project_id_is_stable_and_does_not_resolve_symlinks(self) -> None:
        real = self.aluai / "real"
        real.mkdir()
        link = self.aluai / "link"
        link.symlink_to(real, target_is_directory=True)
        self.assertEqual(project_id_for_path(str(real)), project_id_for_path(str(real) + "/"))
        self.assertNotEqual(project_id_for_path(str(real)), project_id_for_path(str(real / "child")))
        self.assertNotEqual(project_id_for_path(str(link)), project_id_for_path(str(real)))
        self.assertEqual(normalize_path(str(link)), os.path.abspath(link))
        self.assertTrue(set(MARKER_NAMES) >= {".git", "package.json", "pyproject.toml", "Cargo.toml", "go.mod"})
