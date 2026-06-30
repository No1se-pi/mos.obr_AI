from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterable

from app.config import Settings, get_settings


DATA_FINGERPRINT_METADATA_KEY = "data_fingerprint"
DATA_FINGERPRINT_VERSION_METADATA_KEY = "data_fingerprint_version"
DATA_FINGERPRINT_VERSION = 1


def data_source_paths(settings: Settings | None = None) -> list[tuple[str, Path]]:
    settings = settings or get_settings()
    return [
        ("colleges", Path(settings.data_path)),
        ("faq", Path(settings.faq_data_path)),
        ("weeek", Path(settings.weeek_knowledge_path)),
    ]


def compute_data_fingerprint(paths: Iterable[tuple[str, Path]]) -> str:
    digest = hashlib.sha256()
    digest.update(f"mosobr-data-v{DATA_FINGERPRINT_VERSION}\0".encode("utf-8"))

    for label, path in paths:
        digest.update(str(label).encode("utf-8"))
        digest.update(b"\0")
        if not path.exists():
            digest.update(b"<missing>")
            digest.update(b"\0")
            continue

        digest.update(path.read_bytes())
        digest.update(b"\0")

    return digest.hexdigest()


def current_data_fingerprint(settings: Settings | None = None) -> str:
    return compute_data_fingerprint(data_source_paths(settings))
