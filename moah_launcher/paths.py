from __future__ import annotations

import os
from pathlib import Path

from moah_launcher.constants import (
    APP_DIR_NAME,
    DEFAULT_PROJECTS_ROOT,
    SUGGESTED_ROOT_NAMES,
)


def xdg_home(env_name: str, fallback: Path) -> Path:
    value = os.environ.get(env_name, "").strip()
    if not value:
        return fallback
    return Path(value)


def xdg_config_home() -> Path:
    return xdg_home("XDG_CONFIG_HOME", Path.home() / ".config")


def xdg_data_home() -> Path:
    return xdg_home("XDG_DATA_HOME", Path.home() / ".local" / "share")


def app_config_dir(config_home: Path | None = None) -> Path:
    base = config_home if config_home is not None else xdg_config_home()
    return base / APP_DIR_NAME


def app_data_dir(data_home: Path | None = None) -> Path:
    base = data_home if data_home is not None else xdg_data_home()
    return base / APP_DIR_NAME


def normalize_path(path: str) -> str:
    if not isinstance(path, str) or not path.strip():
        raise ValueError("Caminho vazio")
    expanded = os.path.expanduser(path.strip())
    # abspath preserva o nome do link; realpath seguiria o alvo.
    return os.path.normpath(os.path.abspath(expanded))


def is_within(path: str, root: str) -> bool:
    return path == root or path.startswith(root + os.sep)


def category_for(path: str, roots: list[str]) -> str:
    matches = [root for root in roots if is_within(path, root)]
    if not matches:
        return "Manual"
    best = max(matches, key=len)
    return os.path.basename(best) or best


def suggested_source_roots(projects_root: str | None = None) -> list[str]:
    root = projects_root or DEFAULT_PROJECTS_ROOT
    if not os.path.isdir(root):
        return []
    found: list[str] = []
    for name in SUGGESTED_ROOT_NAMES:
        candidate = os.path.join(root, name)
        if os.path.islink(candidate):
            continue
        if os.path.isdir(candidate):
            found.append(normalize_path(candidate))
    return found


def unique_paths(paths: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for path in paths:
        try:
            normalized = normalize_path(path)
        except ValueError:
            continue
        if normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(normalized)
    return ordered
