from __future__ import annotations

import os
import threading
from pathlib import Path

from moah_launcher.catalog import Catalog
from moah_launcher.constants import (
    DEFAULT_CURSOR_BIN,
    DEFAULT_PROJECTS_ROOT,
    SCHEMA_VERSION,
)
from moah_launcher.discovery import DiscoveryResult
from moah_launcher.messages import (
    FILESYSTEM_ROOT_REJECTED,
    GROUP_EMPTY,
    GROUP_NOT_FOUND,
    MANUAL_ONLY,
    PROJECT_NOT_FOUND,
    cursor_missing,
    folder_unavailable,
    partial_group,
    ssd_unavailable,
    symlink_skipped,
)
from moah_launcher.paths import normalize_path, suggested_source_roots, unique_paths
from moah_launcher.persistence import Repository
from moah_launcher.runner import CursorRunner


class LauncherActions:
    """Ações reutilizáveis pela interface e, depois, pelo MOAH.

    Ações de integração: listProjects, searchProjects, openProject, openGroup.
    """

    def __init__(
        self,
        config_home: Path | None = None,
        data_home: Path | None = None,
        projects_root: str | None = None,
        runner: CursorRunner | None = None,
        cursor_bin: str | None = None,
        max_recents: int = 30,
    ) -> None:
        self.repo = Repository(config_home, data_home)
        self._lock = threading.RLock()
        stored = self.repo.read_settings()
        self.settings = self._initial_settings(stored, projects_root, cursor_bin)
        if stored is None and os.path.isdir(self.settings["projectsRoot"]):
            self.repo.save_settings(self.settings)
        elif stored is not None:
            self.repo.save_settings(self.settings)
        self.runner = runner or CursorRunner(self.settings["cursorBin"])
        self.catalog = Catalog(
            self.repo.read_projects(),
            self.repo.read_favorites(),
            self.repo.read_recents(),
            self.repo.read_groups(),
            max_recents=max_recents,
        )
        self._persist_catalog_state()

    def invoke(self, action: str, payload: dict | None = None):
        payload = dict(payload or {})
        if action == "listProjects":
            return self.listProjects(scope=payload.get("scope", "all"))
        if action == "searchProjects":
            return self.searchProjects(
                payload.get("query", ""),
                scope=payload.get("scope", "all"),
            )
        if action == "openProject":
            return self.openProject(payload["projectId"])
        if action == "openGroup":
            return self.openGroup(payload["groupId"])
        raise KeyError(f"Ação desconhecida: {action}")

    def listProjects(self, scope: str = "all") -> list[dict]:
        with self._lock:
            return [self._public(project) for project in self.catalog.projects_for_scope(scope)]

    def searchProjects(self, query: str, scope: str = "all") -> list[dict]:
        with self._lock:
            return [self._public(project) for project in self.catalog.search(query, scope)]

    def openProject(self, project_id: str) -> dict:
        with self._lock:
            project = self.catalog.get_project(project_id)
            if project is None:
                return {
                    "ok": False,
                    "action": "openProject",
                    "projectId": project_id,
                    "name": None,
                    "path": None,
                    "pid": None,
                    "error": PROJECT_NOT_FOUND,
                }
            result = self.runner.open_directory(project["path"])
            if result["ok"]:
                self.catalog.remember(project_id)
                self.repo.save_recents(self.catalog.recents)
            return {
                "ok": result["ok"],
                "action": "openProject",
                "projectId": project_id,
                "name": project["name"],
                "path": result["path"],
                "pid": result["pid"],
                "error": result["error"],
            }

    def openGroup(self, group_id: str) -> dict:
        with self._lock:
            group = self.catalog.get_group(group_id)
            if group is None:
                return {
                    "ok": False,
                    "action": "openGroup",
                    "groupId": group_id,
                    "name": None,
                    "results": [],
                    "error": GROUP_NOT_FOUND,
                }
            if not group["projectIds"]:
                return {
                    "ok": False,
                    "action": "openGroup",
                    "groupId": group_id,
                    "name": group["name"],
                    "results": [],
                    "error": GROUP_EMPTY,
                }
            results = [self.openProject(project_id) for project_id in list(group["projectIds"])]
            failed = [item for item in results if not item["ok"]]
            error = None if not failed else partial_group(len(failed), len(results))
            return {
                "ok": not failed,
                "action": "openGroup",
                "groupId": group_id,
                "name": group["name"],
                "results": results,
                "error": error,
            }

    def list_groups(self) -> list[dict]:
        with self._lock:
            return [self._public_group(group) for group in self.catalog.groups]

    def search_groups(self, query: str) -> list[dict]:
        with self._lock:
            return [self._public_group(group) for group in self.catalog.search_groups(query)]

    def source_roots(self) -> list[str]:
        with self._lock:
            return list(self.settings["sourceRoots"])

    def suggested_roots(self) -> list[str]:
        return suggested_source_roots(self.settings["projectsRoot"])

    def set_source_roots(self, roots: list[str]) -> dict:
        with self._lock:
            saved: list[str] = []
            rejected: list[dict] = []
            for path in unique_paths(roots):
                if path == os.path.abspath(os.sep):
                    rejected.append({"path": path, "error": FILESYSTEM_ROOT_REJECTED})
                    continue
                if os.path.islink(path):
                    rejected.append({"path": path, "error": symlink_skipped(path)})
                    continue
                if os.path.lexists(path) and not os.path.isdir(path):
                    rejected.append({"path": path, "error": folder_unavailable(path)})
                    continue
                saved.append(path)
            self.settings["sourceRoots"] = saved
            self.repo.save_settings(self.settings)
            return {"saved": saved, "rejected": rejected}

    def apply_discovery(self, result: DiscoveryResult) -> None:
        if result.cancelled:
            return
        with self._lock:
            self.catalog.apply_discovery(result)
            self.repo.save_projects(self.catalog.projects)

    def add_manual_project(self, path: str) -> dict:
        with self._lock:
            try:
                normalized = normalize_path(path)
            except ValueError as exc:
                raise ValueError(folder_unavailable(str(path))) from exc
            if os.path.islink(normalized):
                raise ValueError(symlink_skipped(normalized))
            if not os.path.isdir(normalized):
                raise ValueError(folder_unavailable(normalized))
            category = self.catalog.category_for_path(normalized, self.settings["sourceRoots"])
            project = self.catalog.add_manual(normalized, category)
            self.repo.save_projects(self.catalog.projects)
            return self._public(project)

    def remove_manual_project(self, project_id: str) -> None:
        with self._lock:
            try:
                removed = self.catalog.remove_manual(project_id)
            except ValueError as exc:
                raise ValueError(MANUAL_ONLY) from exc
            if removed is None:
                raise KeyError(PROJECT_NOT_FOUND)
            self._persist_catalog_state()

    def toggle_favorite(self, project_id: str) -> bool:
        with self._lock:
            try:
                state = self.catalog.toggle_favorite(project_id)
            except KeyError as exc:
                raise KeyError(PROJECT_NOT_FOUND) from exc
            self.repo.save_favorites(self.catalog.favorite_ids)
            return state

    def save_group(self, name: str, project_ids: list[str], group_id: str | None = None) -> dict:
        with self._lock:
            group = self.catalog.save_group(name, project_ids, group_id)
            self.repo.save_groups(self.catalog.groups)
            return self._public_group(group)

    def delete_group(self, group_id: str) -> None:
        with self._lock:
            if not self.catalog.delete_group(group_id):
                raise KeyError(GROUP_NOT_FOUND)
            self.repo.save_groups(self.catalog.groups)

    def save_window_size(self, width: int, height: int) -> None:
        with self._lock:
            self.settings["window"] = {
                "width": int(width),
                "height": int(height),
            }
            self.repo.save_settings(self.settings)

    def status_report(self) -> dict:
        with self._lock:
            root = self.settings["projectsRoot"]
            ssd_ok = os.path.isdir(root)
            messages: list[str] = []
            missing: list[str] = []
            if not ssd_ok:
                messages.append(ssd_unavailable(root))
            else:
                for source in self.settings["sourceRoots"]:
                    if os.path.islink(source):
                        missing.append(source)
                        messages.append(symlink_skipped(source))
                        continue
                    if not os.path.isdir(source):
                        missing.append(source)
                        messages.append(folder_unavailable(source))
            cursor_bin = self.settings["cursorBin"]
            cursor_ok = os.path.isfile(cursor_bin) and os.access(cursor_bin, os.X_OK)
            if not cursor_ok:
                messages.append(cursor_missing(cursor_bin))
            messages.extend(self.repo.load_warnings)
            return {
                "projectsRoot": root,
                "ssdAvailable": ssd_ok,
                "missingRoots": missing,
                "cursorBin": cursor_bin,
                "cursorAvailable": cursor_ok,
                "projectCount": len(self.catalog.projects),
                "groupCount": len(self.catalog.groups),
                "messages": messages,
                "window": self.settings.get("window"),
            }

    def _initial_settings(
        self,
        stored: dict | None,
        projects_root: str | None,
        cursor_bin: str | None,
    ) -> dict:
        if stored is None:
            root = _clean_root(projects_root or DEFAULT_PROJECTS_ROOT)
            binary = cursor_bin or DEFAULT_CURSOR_BIN
            return {
                "version": SCHEMA_VERSION,
                "cursorBin": binary,
                "projectsRoot": root,
                "sourceRoots": suggested_source_roots(root),
                "window": None,
            }
        root = _clean_root(
            projects_root
            or stored.get("projectsRoot")
            or DEFAULT_PROJECTS_ROOT
        )
        binary = cursor_bin or stored.get("cursorBin") or DEFAULT_CURSOR_BIN
        raw_roots = stored.get("sourceRoots")
        if not isinstance(raw_roots, list):
            raw_roots = []
        roots = [path for path in unique_paths([item for item in raw_roots if isinstance(item, str)])]
        window = stored.get("window") if isinstance(stored.get("window"), dict) else None
        return {
            "version": SCHEMA_VERSION,
            "cursorBin": binary,
            "projectsRoot": root,
            "sourceRoots": roots,
            "window": window,
        }

    def _public(self, project: dict) -> dict:
        return {
            "id": project["id"],
            "name": project["name"],
            "path": project["path"],
            "category": project["category"],
            "source": project["source"],
            "markers": list(project["markers"]),
            "favorite": project["id"] in self.catalog.favorite_ids,
            "available": self._path_available(project["path"]),
        }

    def _public_group(self, group: dict) -> dict:
        by_id = {project["id"]: project for project in self.catalog.projects}
        members = []
        for project_id in group["projectIds"]:
            project = by_id.get(project_id)
            if project:
                members.append(self._public(project))
            else:
                members.append(
                    {
                        "id": project_id,
                        "name": "Projeto ausente",
                        "path": "",
                        "category": "",
                        "source": "missing",
                        "markers": [],
                        "favorite": False,
                        "available": False,
                    }
                )
        return {
            "id": group["id"],
            "name": group["name"],
            "projectIds": list(group["projectIds"]),
            "projects": members,
        }

    def _path_available(self, path: str) -> bool:
        root = self.settings["projectsRoot"]
        if not os.path.isdir(root) and (path == root or path.startswith(root + os.sep)):
            return False
        return os.path.isdir(path)

    def _persist_catalog_state(self) -> None:
        self.repo.save_projects(self.catalog.projects)
        self.repo.save_favorites(self.catalog.favorite_ids)
        self.repo.save_recents(self.catalog.recents)
        self.repo.save_groups(self.catalog.groups)


def _clean_root(path: str) -> str:
    try:
        return normalize_path(path)
    except ValueError:
        return DEFAULT_PROJECTS_ROOT
