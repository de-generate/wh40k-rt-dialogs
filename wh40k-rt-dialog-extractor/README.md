# Rogue Trader dialog extractor

Extracts the dialogs of *Warhammer 40,000: Rogue Trader* (base game + DLC1–3) from an exported blueprint dump and
writes them as JSON or readable text. Requires Python 3.10+ (tested with 3.13), no third-party packages.

## Input

Put the export in `data/`:

```
data/
├── Blueprints/World/Dialogs/…   base-game dialog blueprints (*.jbp)
├── Blueprints/DLC/DLC1…DLC3/…   DLC dialog blueprints
└── Strings/Blueprints/…         localized strings (*.json), same layout
```

Each AssetId may only exist once. The build aborts if a folder was accidentally copied twice.

## Usage

Run the commands from this directory (defaults are relative to it). Alternatively, `pip install -e .` installs the
package and an `rt-dialogs` command that works anywhere.

Build the dialog database `dialogs.json` (takes ~30–80 s; all other commands then load it in a few seconds):

```bash
python -m rt_dialogs build --verify
```

Print a summary (`--issues N` lists parse problems such as missing strings):

```bash
python -m rt_dialogs stats --issues 20
```

Write a human-readable script of all dialogs:

```bash
python -m rt_dialogs output labeled-script-single
```

`output` rebuilds `dialogs.json` automatically if it's missing or `data/` changed. Options of
`labeled-script-single`:

| Option | Default | Meaning |
|---|---|---|
| `--lang` | `enGB` | Locale: `enGB`, `deDE`, `frFR`, `esES`, `ruRU`, `zhCN`, `jaJP`, `trTR`, `dev` |
| `--dialogs` | `skip-deleted` | `all`, `skip-deleted`, or comma-separated dialog names / AssetIds / paths |
| `--separator` | `\n\n\n` | Text between dialogs (`\n`, `\t`, `\\` escapes) |
| `--output-file` | `dialogs-labeled-script-single.txt` | Output file |

## Reading the labeled script

```
[A] ------------------------------------------------------------------
  Kunrad: "Allow me to introduce myself…"          NPC line
    (actions: ShowNewTutorial)                      game actions
  1. "My name is <Name>."                           player answers
     if: CheckConditionsHolder(4f6e6056)            when the answer is shown
     → [B]                                          continue at section [B]
  2. [Persuasion, Hard] "…"   <Faith +3>   (once)   skill check, soul mark, show once
     CHECK [Persuasion, Hard]
     success: …
     failure: …
```

* Lines reachable from several places are printed once as a labeled section `[X]`, and other places jump there.
* `First that applies:` lists alternatives; the first one whose condition holds is played.
* `*…*` is narration. `NPC:` means the conversation partner the player clicked on (not named in the data).
* `[END]` ends the dialog.

## Files

* `dialogs.json`: the full database (all dialogs incl. deleted ones, all nodes, all locales, conditions and actions).
  Load it in Python with `rt_dialogs.load_cache('dialogs.json')`.
* `DIALOG_STRUCTURE.md`: how the raw export is structured.

## Tests

```bash
python -m unittest discover -s tests -t .
```
