from __future__ import annotations

import os
from datetime import datetime, timezone

from moah_launcher.constants import MARKER_NAMES, MAX_RECENTS
from moah_launcher.discovery import DiscoveryResult
from moah_launcher.ids import new_group_id, project_id_for_path
from moah_launcher.messages import GROUP_NEEDS_NAME, GROUP_NEEDS_PROJECT
from moah_launcher.paths import category_for, is_within, normalize_path

PROJECT_FIELDS = ("id", "name", "path", "category", "source", "markers")


def project_sort_key(project: dict) -> tuple[str, str, str]:
    return (
        str(project.get("category", "")).casefold(),
        str(project.get("name", "")).casefold(),
        str(project.get("path", "")),
    )


def coerce_project(raw: dict) -> dict | None:
    path = raw.get("path")
    name = raw.get("name")
    if not isinstance(path, str) or not isinstance(name, str) or not path or not name:
        return None
    try:
        normalized = normalize_path(path)
    except ValueError:
        return None
    source = raw.get("source")
    if source not in ("manual", "discovered"):
        source = "discovered"
    category = raw.get("category")
    if not isinstance(category, str) or not category.strip():
        category = "Manual"
    markers = raw.get("markers") or []
    if not isinstance(markers, list):
        markers = []
    clean_markers = [item for item in markers if isinstance(item, str) and item in MARKER_NAMES]
    return {
        "id": project_id_for_path(normalized),
        "name": os.path.basename(normalized) or name,
        "path": normalized,
        "category": category,
        "source": source,
        "markers": clean_markers,
    }


def remap_id(old_id: str, mapping: dict[str, str]) -> str:
    return mapping.get(old_id, old_id)


class Catalog:
    def __init__(
        self,
        projects: list[dict] | None = None,
        favorite_ids: list[str] | None = None,
        recents: list[dict] | None = None,
        groups: list[dict] | None = None,
        max_recents: int = MAX_RECENTS,
    ) -> None:
        self.max_recents = max_recents
        self.projects: list[dict] = []
        self.favorite_ids: list[str] = []
        self.recents: list[dict] = []
        self.groups: list[dict] = []
        self.replace_state(projects or [], favorite_ids or [], recents or [], groups or [])

    def replace_state(
        self,
        projects: list[dict],
        favorite_ids: list[str],
        recents: list[dict],
        groups: list[dict],
    ) -> dict[str, str]:
        id_map: dict[str, str] = {}
        by_path: dict[str, dict] = {}
        for raw in projects:
            if not isinstance(raw, dict):
                continue
            previous = raw.get("id")
            project = coerce_project(raw)
            if project is None:
                continue
            if isinstance(previous, str):
                id_map[previous] = project["id"]
            current = by_path.get(project["path"])
            if current and current["source"] == "manual":
                project["source"] = "manual"
            by_path[project["path"]] = project
        self.projects = sorted(by_path.values(), key=project_sort_key)
        self.favorite_ids = _unique(
            remap_id(project_id, id_map)
            for project_id in favorite_ids
            if isinstance(project_id, str)
        )
        self.favorite_ids = [project_id for project_id in self.favorite_ids if project_id]
        cleaned_recents: list[dict] = []
        seen_recent: set[str] = set()
        for entry in recents:
            if not isinstance(entry, dict):
                continue
            project_id = entry.get("projectId")
            opened_at = entry.get("openedAt")
            if not isinstance(project_id, str) or not isinstance(opened_at, str):
                continue
            project_id = remap_id(project_id, id_map)
            if project_id in seen_recent:
                continue
            seen_recent.add(project_id)
            cleaned_recents.append({"projectId": project_id, "openedAt": opened_at})
        self.recents = cleaned_recents[: self.max_recents]
        self.groups = []
        for raw_group in groups:
            group = self._coerce_group(raw_group, id_map)
            if group:
                self.groups.append(group)
        return id_map

    def projects_for_scope(self, scope: str) -> list[dict]:
        if scope == "all":
            return sorted(self.projects, key=project_sort_key)
        by_id = {project["id"]: project for project in self.projects}
        if scope == "favorites":
            return [by_id[project_id] for project_id in self.favorite_ids if project_id in by_id]
        if scope == "recents":
            ordered = []
            for entry in self.recents:
                project = by_id.get(entry["projectId"])
                if project:
                    ordered.append(project)
            return ordered
        raise ValueError(f"Escopo desconhecido: {scope}")

    def search(self, query: str, scope: str = "all") -> list[dict]:
        tokens = query.casefold().split()
        items = self.projects_for_scope(scope)
        if not tokens:
            return list(items)
        matched = [project for project in items if _matches(project, tokens)]
        if scope == "all":
            matched.sort(key=project_sort_key)
        return matched

    def search_groups(self, query: str) -> list[dict]:
        tokens = query.casefold().split()
        if not tokens:
            return list(self.groups)
        by_id = {project["id"]: project for project in self.projects}
        matched = []
        for group in self.groups:
            parts = [group["name"]]
            for project_id in group["projectIds"]:
                project = by_id.get(project_id)
                if project:
                    parts.extend([project["name"], project["category"], project["path"]])
            haystack = "\n".join(parts).casefold()
            if all(token in haystack for token in tokens):
                matched.append(group)
        return matched

    def get_project(self, project_id: str) -> dict | None:
        for project in self.projects:
            if project["id"] == project_id:
                return project
        return None

    def get_group(self, group_id: str) -> dict | None:
        for group in self.groups:
            if group["id"] == group_id:
                return group
        return None

    def add_manual(self, path: str, category: str | None = None) -> dict:
        normalized = normalize_path(path)
        for project in self.projects:
            if project["path"] == normalized:
                return project
        project = {
            "id": project_id_for_path(normalized),
            "name": os.path.basename(normalized) or normalized,
            "path": normalized,
            "category": category or "Manual",
            "source": "manual",
            "markers": [],
        }
        self.projects.append(project)
        self.projects.sort(key=project_sort_key)
        return project

    def remove_manual(self, project_id: str) -> dict | None:
        for index, project in enumerate(self.projects):
            if project["id"] == project_id:
                if project["source"] != "manual":
                    raise ValueError("manual-only")
                removed = self.projects.pop(index)
                self.favorite_ids = [item for item in self.favorite_ids if item != project_id]
                self.recents = [item for item in self.recents if item["projectId"] != project_id]
                for group in self.groups:
                    group["projectIds"] = [
                        item for item in group["projectIds"] if item != project_id
                    ]
                return removed
        return None

    def toggle_favorite(self, project_id: str) -> bool:
        if self.get_project(project_id) is None:
            raise KeyError(project_id)
        if project_id in self.favorite_ids:
            self.favorite_ids = [item for item in self.favorite_ids if item != project_id]
            return False
        self.favorite_ids.append(project_id)
        return True

    def remember(self, project_id: str, opened_at: str | None = None) -> None:
        moment = opened_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.recents = [entry for entry in self.recents if entry["projectId"] != project_id]
        self.recents.insert(0, {"projectId": project_id, "openedAt": moment})
        del self.recents[self.max_recents :]

    def apply_discovery(self, result: DiscoveryResult) -> None:
        scanned = list(result.scanned_roots)
        found_paths = {project.path for project in result.projects}
        kept: dict[str, dict] = {}
        for project in self.projects:
            under_scanned = any(is_within(project["path"], root) for root in scanned)
            if project["source"] == "discovered" and under_scanned and project["path"] not in found_paths:
                continue
            kept[project["path"]] = project
        for found in result.projects:
            previous = kept.get(found.path)
            kept[found.path] = {
                "id": project_id_for_path(found.path),
                "name": found.name,
                "path": found.path,
                "category": found.category,
                "source": "manual" if previous and previous["source"] == "manual" else "discovered",
                "markers": list(found.markers),
            }
        self.projects = sorted(kept.values(), key=project_sort_key)

    def save_group(
        self,
        name: str,
        project_ids: list[str],
        group_id: str | None = None,
    ) -> dict:
        clean_name = name.strip()
        if not clean_name:
            raise ValueError(GROUP_NEEDS_NAME)
        known = {project["id"] for project in self.projects}
        ids: list[str] = []
        for project_id in project_ids:
            if project_id in known and project_id not in ids:
                ids.append(project_id)
        if group_id:
            group = self.get_group(group_id)
            if group is None:
                raise KeyError(group_id)
            for project_id in group["projectIds"]:
                if project_id not in known and project_id not in ids:
                    ids.append(project_id)
            if not ids:
                raise ValueError(GROUP_NEEDS_PROJECT)
            group["name"] = clean_name
            group["projectIds"] = ids
            return group
        if not ids:
            raise ValueError(GROUP_NEEDS_PROJECT)
        group = {"id": new_group_id(), "name": clean_name, "projectIds": ids}
        self.groups.append(group)
        return group

    def delete_group(self, group_id: str) -> bool:
        for index, group in enumerate(self.groups):
            if group["id"] == group_id:
                del self.groups[index]
                return True
        return False

    def category_for_path(self, path: str, roots: list[str]) -> str:
        try:
            normalized = normalize_path(path)
        except ValueError:
            return "Manual"
        return category_for(normalized, roots)

    def _coerce_group(self, raw: dict, id_map: dict[str, str]) -> dict | None:
        if not isinstance(raw, dict):
            return None
        name = raw.get("name")
        group_id = raw.get("id")
        project_ids = raw.get("projectIds")
        if not isinstance(name, str) or not name.strip():
            return None
        if not isinstance(group_id, str) or not group_id.startswith("grp_"):
            group_id = new_group_id()
        if not isinstance(project_ids, list):
            project_ids = []
        cleaned: list[str] = []
        for project_id in project_ids:
            if not isinstance(project_id, str):
                continue
            mapped = remap_id(project_id, id_map)
            if mapped not in cleaned:
                cleaned.append(mapped)
        return {"id": group_id, "name": name.strip(), "projectIds": cleaned}


def _matches(project: dict, tokens: list[str]) -> bool:
    haystack = "\n".join(
        [project["name"], project["category"], project["path"]]
    ).casefold()
    return all(token in haystack for token in tokens)


def _unique(items) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        ordered.append(item)
    return ordered
