from __future__ import annotations

import hashlib
import uuid

from moah_launcher.paths import normalize_path


def project_id_for_path(path: str) -> str:
    normalized = normalize_path(path)
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:20]
    return f"prj_{digest}"


def new_group_id() -> str:
    return f"grp_{uuid.uuid4().hex[:20]}"
