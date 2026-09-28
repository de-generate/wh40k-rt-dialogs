"""Helpers shared by output formats."""

from __future__ import annotations

import argparse
import re
import sys

from ..model import Dialog, DialogDatabase


def add_dialog_selection(
    p: argparse.ArgumentParser, default: str = "skip-deleted"
) -> None:
    p.add_argument(
        "--dialogs",
        default=default,
        metavar="all|skip-deleted|NAME[,NAME…]",
        help='which dialogs to output: "all", "skip-deleted" (everything except editor-deleted '
        "dialogs), or a comma-separated list of dialog names (entry-point file name without "
        f".jbp), AssetIds or paths (default: {default})",
    )


def select_dialogs(db: DialogDatabase, spec: str) -> list[Dialog]:
    spec = spec.strip()
    if spec == "all":
        return list(db.dialogs)
    if spec == "skip-deleted":
        return [d for d in db.dialogs if not d.deleted]
    wanted = [w.strip() for w in spec.split(",") if w.strip()]
    selected: dict[str, Dialog] = {}
    for w in wanted:
        key = w.replace("\\", "/").removesuffix(".jbp")
        hits = [
            d
            for d in db.dialogs
            if d.name.strip() == key
            or d.id == key
            or d.path.removesuffix(".jbp").endswith(key)
        ]
        if not hits:
            print(f"warning: no dialog named {w!r}", file=sys.stderr)
        elif len(hits) > 1:
            print(
                f"warning: {w!r} matches {len(hits)} dialogs, including all: "
                + ", ".join(d.path for d in hits),
                file=sys.stderr,
            )
        for d in hits:
            selected.setdefault(d.id, d)
    order = {d.id: i for i, d in enumerate(db.dialogs)}
    return sorted(selected.values(), key=lambda d: order[d.id])


_ESCAPES = {"n": "\n", "t": "\t", "\\": "\\"}


def decode_escapes(s: str) -> str:
    r"""Turn the escapes \n, \t and \\ into the characters they stand for."""
    return re.sub(r"\\([nt\\])", lambda m: _ESCAPES[m.group(1)], s)
