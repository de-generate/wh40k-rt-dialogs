# Notes for agents: extractor

## What this project is

A tool that extracts all conversations from the video game *Warhammer 40,000: Rogue Trader* (base game + DLC1–3).
The input in `data/` is an export of the game's Unity blueprints: each dialog is a graph of JSON files (NPC lines,
player answers, skill checks, conditions, actions), and the text lives in separate localized string files (9 locales).
The tool works in two stages:

1. `python -m rt_dialogs build` parses the whole export into one database, `dialogs.json`. It works as a cache:
   parsing takes ~30–80 s, loading the cache ~4 s.
2. `python -m rt_dialogs output <format>` renders the database in other formats. So far there are
   `labeled-script-single` (all dialogs as a readable script in one text file) and `explorer-bundle` (the zip the
   explorer loads, spec in `EXPLORER_BUNDLE.md`).

Environment: Python 3.13 on Windows, standard library only (no pytest; tests use `unittest`). This directory is one
project in a larger git repository (see `../AGENTS.md`); run commands from here. `data/` and generated files are
git-ignored.

## Read first

* `DIALOG_STRUCTURE.md`: format of the raw export, which is the source of truth for semantics. Keep it updated
  when you learn something new about the data. Mark facts inferred from data (not game code) as such.
* `README.md`: user-facing usage.
* `EXPLORER_BUNDLE.md`: spec of the `explorer-bundle` format consumed by `../wh40k-rt-dialog-explorer`. Keep it in
  sync with the code and bump its `version` on changes the explorer must know about.

## Layout

| Path | Purpose |
|---|---|
| `rt_dialogs/model.py` | Dataclasses (`DialogDatabase` → `Dialog` → nodes `Cue`, `Answer`, …), `node_children()` |
| `rt_dialogs/parse.py` | Raw export → model: parallel file reading, string/speaker resolution, reachability, `issues` |
| `rt_dialogs/serialize.py` | Generic dataclass ⇄ JSON (defaults omitted, `kind` discriminator for nodes) |
| `rt_dialogs/cache.py` | `save_cache` / `load_cache` / `load_or_build` (fingerprint of paths+sizes+mtimes) |
| `rt_dialogs/describe.py` | Shared text helpers: markup cleanup, condition/action/skill/soul-mark descriptions |
| `rt_dialogs/formats/` | Output formats; register new ones in `formats/__init__.py` `FORMATS` |
| `rt_dialogs/cli.py` | `build`, `stats`, `output <format>` |
| `tests/` | Synthetic mini export (`tests/test_cache.py: make_export`) + format tests |
| `pyproject.toml` | Packaging (`pip install -e .` → `rt-dialogs` command; lets other projects import `rt_dialogs`) |

## Working with the data

* `data/` has ~117k small files and the filesystem is slow. For analysis, prefer loading `dialogs.json` via
  `rt_dialogs.load_cache` (~4 s) over listing or reading the raw files from the shell, and rebuild only when the
  parser changes.
* Prefer identifying blueprints by `$type` over file names. File names are inconsistent and some contain spaces.
* Prefer resolving strings by key (global index) over paths. `m_JsonPath` is a fallback only.
* `Continue` takes precedence over a cue's `Answers` (inferred, see DIALOG_STRUCTURE.md §3.2).
* Graphs have cycles and shared nodes, so traversals need to track visited nodes.
* Unit/speaker, quest, etude and portrait blueprints are *not* in the export; references to them stay opaque ids.

## Conventions

* Changing the model or the parser's output: bump `SCHEMA_VERSION` in `model.py` and rebuild `dialogs.json`.
* Every output format takes `--cache`/`--data` (added by the CLI) plus its own options, and uses
  `formats/common.py` for `--dialogs` selection.
* Keep speaker names internal (`AbelardCompanion`); unknown speakers render as `NPC` (user decision).
* Add a test to `tests/` for new behavior. Run the full build (`python -m rt_dialogs build --verify`) after parser
  changes and check `stats --issues`.
