"""Reading and writing ``dialogs.json`` (the parsed dialog database)."""

from __future__ import annotations

import json
import os
from pathlib import Path

from . import serialize
from .model import SCHEMA_VERSION, DialogDatabase
from .parse import Progress, parse_export, source_fingerprint


class CacheError(Exception):
    pass


def save_cache(db: DialogDatabase, path: str | os.PathLike) -> None:
    """Write ``db`` as indented JSON. The file is replaced atomically."""
    path = Path(path)
    tmp = path.with_name(path.name + ".tmp")
    data = {
        "schema_version": db.schema_version,
        **serialize.to_json(db),
    }  # always written
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    os.replace(tmp, path)


def load_cache(path: str | os.PathLike) -> DialogDatabase:
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    version = data.get("schema_version") if isinstance(data, dict) else None
    if version != SCHEMA_VERSION:
        raise CacheError(
            f"{path} has schema version {version}, expected {SCHEMA_VERSION}; rebuild it"
        )
    return serialize.from_json(DialogDatabase, data)


def is_stale(db: DialogDatabase, data_root: str | os.PathLike) -> bool:
    """True if the files below ``data_root`` changed since ``db`` was built."""
    return db.source_fingerprint != source_fingerprint(Path(data_root))


def load_or_build(
    data_root: str | os.PathLike,
    cache_path: str | os.PathLike,
    *,
    rebuild: bool = False,
    check_stale: bool = True,
    workers: int = 16,
    progress: Progress = lambda s: None,
) -> DialogDatabase:
    """Load the cache, (re)building it from the export when missing, outdated or ``rebuild`` is set."""
    cache_path = Path(cache_path)
    if not rebuild and cache_path.exists():
        try:
            db = load_cache(cache_path)
        except (CacheError, ValueError, TypeError, KeyError) as e:
            progress(f"cache unusable ({e}); rebuilding")
        else:
            if not check_stale or not is_stale(db, data_root):
                return db
            progress("input files changed since the cache was built; rebuilding")
    db = parse_export(data_root, workers=workers, progress=progress)
    save_cache(db, cache_path)
    return db
