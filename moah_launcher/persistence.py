from __future__ import annotations

import json
import os
from pathlib import Path

from moah_launcher.constants import SCHEMA_VERSION
from moah_launcher.messages import unreadable_file
from moah_launcher.paths import app_config_dir, app_data_dir


class Repository:
    """Lê e grava somente nos diretórios XDG do usuário."""

    def __init__(
        self,
        config_home: Path | None = None,
        data_home: Path | None = None,
    ) -> None:
        self.config_dir = app_config_dir(config_home)
        self.data_dir = app_data_dir(data_home)
        self.load_warnings: list[str] = []

    @property
    def settings_path(self) -> Path:
        return self.config_dir / "settings.json"

    @property
    def catalog_path(self) -> Path:
        return self.data_dir / "catalog.json"

    @property
    def favorites_path(self) -> Path:
        return self.data_dir / "favorites.json"

    @property
    def recents_path(self) -> Path:
        return self.data_dir / "recents.json"

    @property
    def groups_path(self) -> Path:
        return self.data_dir / "groups.json"

    def read_settings(self) -> dict | None:
        return self._read_document(self.settings_path)

    def save_settings(self, settings: dict) -> None:
        self._write(self.settings_path, settings)

    def read_projects(self) -> list[dict]:
        document = self._read_document(self.catalog_path)
        if not document:
            return []
        projects = document.get("projects")
        if not isinstance(projects, list):
            self.load_warnings.append(unreadable_file(self.catalog_path.name))
            return []
        return [item for item in projects if isinstance(item, dict)]

    def save_projects(self, projects: list[dict]) -> None:
        self._write(
            self.catalog_path,
            {"version": SCHEMA_VERSION, "projects": projects},
        )

    def read_favorites(self) -> list[str]:
        document = self._read_document(self.favorites_path)
        if not document:
            return []
        ids = document.get("projectIds")
        if not isinstance(ids, list):
            return []
        return [item for item in ids if isinstance(item, str)]

    def save_favorites(self, project_ids: list[str]) -> None:
        self._write(
            self.favorites_path,
            {"version": SCHEMA_VERSION, "projectIds": project_ids},
        )

    def read_recents(self) -> list[dict]:
        document = self._read_document(self.recents_path)
        if not document:
            return []
        entries = document.get("entries")
        if not isinstance(entries, list):
            return []
        return [item for item in entries if isinstance(item, dict)]

    def save_recents(self, entries: list[dict]) -> None:
        self._write(
            self.recents_path,
            {"version": SCHEMA_VERSION, "entries": entries},
        )

    def read_groups(self) -> list[dict]:
        document = self._read_document(self.groups_path)
        if not document:
            return []
        groups = document.get("groups")
        if not isinstance(groups, list):
            return []
        return [item for item in groups if isinstance(item, dict)]

    def save_groups(self, groups: list[dict]) -> None:
        self._write(
            self.groups_path,
            {"version": SCHEMA_VERSION, "groups": groups},
        )

    def _read_document(self, path: Path) -> dict | None:
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self._preserve_corrupt(path)
            return None
        if not isinstance(data, dict):
            self._preserve_corrupt(path)
            return None
        return data

    def _preserve_corrupt(self, path: Path) -> None:
        backup = path.with_name(path.name + ".corrupt")
        try:
            os.replace(path, backup)
        except OSError:
            backup = path
        self.load_warnings.append(unreadable_file(backup.name))

    def _write(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.tmp")
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
