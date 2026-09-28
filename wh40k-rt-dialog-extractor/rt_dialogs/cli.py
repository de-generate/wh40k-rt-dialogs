"""Command line interface: ``python -m rt_dialogs <command> …``."""

from __future__ import annotations

import argparse
import collections
import sys
import time
from pathlib import Path

from .cache import CacheError, is_stale, load_cache, load_or_build, save_cache
from .formats import FORMATS
from .model import DialogDatabase
from .parse import ExportError, parse_export


def _progress(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def cmd_build(args: argparse.Namespace) -> int:
    start = time.perf_counter()
    db = parse_export(args.data, workers=args.workers, progress=_progress)
    _progress(f"parsed in {time.perf_counter() - start:.0f}s; writing {args.cache}")
    save_cache(db, args.cache)
    size = Path(args.cache).stat().st_size / 1e6
    _progress(f"wrote {args.cache} ({size:.1f} MB)")
    if args.verify:
        start = time.perf_counter()
        loaded = load_cache(args.cache)
        _progress(f"reloaded in {time.perf_counter() - start:.1f}s")
        if loaded != db:
            _progress("VERIFY FAILED: reloaded database differs from the parsed one")
            return 1
        _progress("verify ok: reloaded database equals the parsed one")
    print_stats(db)
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    start = time.perf_counter()
    db = load_cache(args.cache)
    _progress(f"loaded {args.cache} in {time.perf_counter() - start:.1f}s")
    if args.data and is_stale(db, args.data):
        _progress(
            f'warning: files in {args.data} changed since the cache was built (run "build")'
        )
    print_stats(db, issues=args.issues)
    return 0


def cmd_output(args: argparse.Namespace) -> int:
    start = time.perf_counter()
    if Path(args.data).is_dir():
        db = load_or_build(
            args.data, args.cache, workers=args.workers, progress=_progress
        )
    else:
        db = load_cache(args.cache)
    _progress(f"loaded dialog database in {time.perf_counter() - start:.1f}s")
    return FORMATS[args.format].run(db, args)


def print_stats(db: DialogDatabase, issues: int = 0) -> None:
    by_source = collections.Counter(d.source for d in db.dialogs)
    deleted = sum(d.deleted for d in db.dialogs)
    kinds = collections.Counter(n.KIND for d in db.dialogs for n in d.nodes.values())
    nodes = [n for d in db.dialogs for n in d.nodes.values()]
    texts = [n.text for n in nodes if getattr(n, "text", None)]
    print(f"generated:  {db.generated_at} from {db.data_root}")
    print(
        f"dialogs:    {len(db.dialogs)} ({', '.join(f'{s} {c}' for s, c in sorted(by_source.items()))}), "
        f"{deleted} deleted"
    )
    print(
        f"nodes:      {len(nodes)} ({', '.join(f'{k} {c}' for k, c in kinds.most_common())})"
    )
    print(
        f"            {sum(n.deleted for n in nodes)} deleted, {sum(not n.reachable for n in nodes)} unreachable"
    )
    print(
        f"texts:      {len(texts)} cue/answer texts, {sum(t.missing for t in texts)} missing"
    )
    print(f"banters:    {len(db.banters)} in {len(db.banter_lists)} lists")
    print(f"speakers:   {len(db.speakers)} unit blueprints with a known name")
    print(f"locales:    {', '.join(db.locales)}")
    print(f"issues:     {len(db.issues)}")
    for line in db.issues[:issues]:
        print("  " + line)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m rt_dialogs", description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)

    b = sub.add_parser(
        "build", help="parse the export and write the dialogs.json cache"
    )
    b.add_argument(
        "--data",
        default="data",
        help="export root containing Blueprints/ and Strings/ (default: data)",
    )
    b.add_argument(
        "--cache",
        default="dialogs.json",
        help="cache file to write (default: dialogs.json)",
    )
    b.add_argument(
        "--workers", type=int, default=16, help="parallel file readers (default: 16)"
    )
    b.add_argument(
        "--verify", action="store_true", help="reload the written cache and compare"
    )
    b.set_defaults(func=cmd_build)

    s = sub.add_parser("stats", help="load the cache and print a summary")
    s.add_argument("--cache", default="dialogs.json")
    s.add_argument(
        "--data", help="also check whether the export changed since the cache was built"
    )
    s.add_argument(
        "--issues",
        type=int,
        default=0,
        metavar="N",
        help="print the first N parse issues",
    )
    s.set_defaults(func=cmd_stats)

    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--cache",
        default="dialogs.json",
        help="dialog database; built (or rebuilt when the export changed) automatically "
        "(default: dialogs.json)",
    )
    common.add_argument(
        "--data",
        default="data",
        help="export root, used to build/refresh the cache; skipped if the folder does not "
        "exist (default: data)",
    )
    common.add_argument("--workers", type=int, default=16, help=argparse.SUPPRESS)
    o = sub.add_parser("output", help="write the dialogs in a human-readable format")
    fmts = o.add_subparsers(dest="format", required=True, metavar="FORMAT")
    for fmt in FORMATS.values():
        fp = fmts.add_parser(
            fmt.name, help=fmt.help, description=fmt.help, parents=[common]
        )
        fmt.add_arguments(fp)
    o.set_defaults(func=cmd_output)

    args = p.parse_args(argv)
    try:
        return args.func(args)
    except (ExportError, CacheError, FileNotFoundError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
