from __future__ import annotations

import os
from dataclasses import dataclass

from moah_launcher.constants import IGNORED_DIRS, MARKER_NAMES
from moah_launcher.messages import folder_unavailable, no_permission, symlink_skipped
from moah_launcher.paths import category_for, normalize_path, unique_paths

MARKER_SET = frozenset(MARKER_NAMES)


@dataclass(frozen=True)
class FoundProject:
    path: str
    name: str
    category: str
    markers: tuple[str, ...]


@dataclass(frozen=True)
class DiscoveryResult:
    projects: tuple[FoundProject, ...]
    scanned_roots: tuple[str, ...]
    missing_roots: tuple[str, ...]
    warnings: tuple[str, ...]
    directories_visited: int
    cancelled: bool


def discover_projects(
    roots: list[str],
    on_progress=None,
    should_cancel=None,
) -> DiscoveryResult:
    """Varre só as raízes recebidas. Não segue links e não entra nas pastas ignoradas."""
    normalized_roots = unique_paths(roots)
    found: dict[str, FoundProject] = {}
    scanned: list[str] = []
    missing: list[str] = []
    warnings: list[str] = []
    visited = 0
    # Pais primeiro, para a categoria mais específica vencer em raízes sobrepostas.
    ordered = sorted(normalized_roots, key=len)

    for root in ordered:
        if should_cancel and should_cancel():
            return _cancelled(visited)
        if os.path.islink(root):
            warnings.append(symlink_skipped(root))
            continue
        if not os.path.isdir(root):
            missing.append(root)
            warnings.append(folder_unavailable(root))
            continue
        if on_progress:
            on_progress(f"Lendo {os.path.basename(root) or root}…")
        completed, visited = _scan_root(
            root,
            ordered,
            found,
            warnings,
            visited,
            on_progress,
            should_cancel,
        )
        if not completed:
            return _cancelled(visited)
        scanned.append(root)

    projects = tuple(sorted(found.values(), key=_sort_key))
    return DiscoveryResult(
        projects=projects,
        scanned_roots=tuple(scanned),
        missing_roots=tuple(missing),
        warnings=tuple(warnings),
        directories_visited=visited,
        cancelled=False,
    )


def _scan_root(
    root: str,
    roots: list[str],
    found: dict[str, FoundProject],
    warnings: list[str],
    visited: int,
    on_progress,
    should_cancel,
) -> tuple[bool, int]:
    stack = [root]
    while stack:
        if should_cancel and should_cancel():
            return False, visited
        current = stack.pop()
        visited += 1
        if on_progress and visited % 100 == 0:
            on_progress(f"Lendo {os.path.basename(root) or root}… ({visited} pastas)")
        try:
            with os.scandir(current) as iterator:
                entries = list(iterator)
        except OSError:
            warnings.append(no_permission(current))
            continue

        present: set[str] = set()
        children: list[str] = []
        for entry in entries:
            name = entry.name
            try:
                is_symlink = entry.is_symlink()
            except OSError:
                continue
            if name in MARKER_SET:
                present.add(name)
            if is_symlink or name in IGNORED_DIRS:
                continue
            try:
                is_dir = entry.is_dir(follow_symlinks=False)
            except OSError:
                continue
            if is_dir:
                children.append(entry.path)

        if present:
            path = normalize_path(current)
            markers = tuple(name for name in MARKER_NAMES if name in present)
            found[path] = FoundProject(
                path=path,
                name=os.path.basename(path) or path,
                category=category_for(path, roots),
                markers=markers,
            )
        for child in reversed(children):
            stack.append(child)
    return True, visited


def _cancelled(visited: int) -> DiscoveryResult:
    return DiscoveryResult(
        projects=(),
        scanned_roots=(),
        missing_roots=(),
        warnings=(),
        directories_visited=visited,
        cancelled=True,
    )


def _sort_key(project: FoundProject) -> tuple[str, str, str]:
    return (project.category.casefold(), project.name.casefold(), project.path)
