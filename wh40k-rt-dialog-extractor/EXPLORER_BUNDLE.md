# Explorer bundle format (version 1)

The compact export that `wh40k-rt-dialog-explorer` loads. The extractor owns this format; the explorer follows it.
Status: specified, not yet implemented.

Design goals:

* One file the user loads into the browser once (stored in IndexedDB).
* Random access: the explorer reads single zip entries on demand, never the whole bundle at once.
* Locale-independent structure, per-locale text.
* Everything the player needs is resolved ahead of time, so opening a dialog never requires reading other dialogs.

## 1. Command

```
python -m rt_dialogs output explorer-bundle [--locales LOC[,LOC…]] [--dialogs …] [--output-file FILE]
```

| Option | Default | Meaning |
|---|---|---|
| `--locales` | all locales except `dev` | locales to include, e.g. `enGB,deDE` (~10 MB raw / ~4 MB zipped each) |
| `--dialogs` | `all` | usual selection (`formats/common.py`); unlike other formats, deleted dialogs are included by default and flagged, so the explorer can offer a toggle |
| `--output-file` | `dialogs-explorer-bundle.zip` | file to write |

`enGB` is always used as the fallback text source, even when it isn't among `--locales`.

## 2. Zip layout

```
manifest.json
index.json
dialogs/<dialogId>.json
strings/<locale>.json
```

* Entries are deflate-compressed, UTF-8, minified JSON.
* Ids are the game's AssetIds (32 hex characters), as in `dialogs.json`.
* Optional fields are omitted when they have their default value (`false`, empty, `null`), as in `dialogs.json`.

## 3. `manifest.json`

```jsonc
{
  "format": "rt-dialogs-explorer-bundle",
  "version": 1,
  "generatedAt": "2026-09-28T12:00:00Z",
  "sourceFingerprint": "…",           // dialogs.json source_fingerprint
  "locales": ["deDE", "enGB", …],
  "fallbackLocale": "enGB",
  "companions": ["AbelardCompanion", …],   // every companion referenced by a condition (for later settings)
  "counts": { "dialogs": 1092, "nodes": 58000 }
}
```

`version` is bumped on every change the explorer must know about. The explorer rejects bundles with a version it
doesn't support and tells the user to re-export with a matching extractor.

## 4. `index.json`

Everything needed to list, search and filter dialogs without opening them.

```jsonc
{ "dialogs": [ {
  "id": "25ddc6b8…",
  "name": "KunradIntroduction",
  "path": "World/Dialogs/Ch0_Prologue/KunradIntroduction",  // directory, without "Blueprints/"
  "tags": ["Ch0_Prologue"],
  "chapter": 0,                        // from a Ch<N> tag; absent if none
  "source": "World",                   // World | DLC1 | DLC2 | DLC3
  "type": "Common",                    // Common | Book | StarSystemEvent | Epilog
  "deleted": false,
  "nodes": 42,
  "speakers": ["Kunrad", "AbelardCompanion"]
} ] }
```

`tags` are the segments of `path` after removing the prefixes `World/Dialogs/` or `DLC/`, the segment
`Narrative`, and a last segment equal to the dialog name. Example: `DLC/DLC1/Narrative/Bridge/MasterOfDiscipline`
→ `["DLC1", "Bridge"]`.

## 5. `dialogs/<id>.json`

```jsonc
{
  "id": "25ddc6b8…",
  "name": "KunradIntroduction",
  "deleted": false,
  "comment": "…",
  "if": <group>,                       // conditions to start the dialog (display only)
  "start": <cue list>,
  "actions": { "start": [], "finish": [], "replace": [] },
  "nodes": { "<nodeId>": <node>, … }
}
```

Only nodes reachable from `start` are included. Reachable shadow-deleted nodes are included with `deleted: true`.
An edge may point to an id that is not in `nodes` (a missing asset). The explorer shows it as a missing node and
ends the branch there.

### 5.1 Common building blocks

| Name | Shape | Meaning |
|---|---|---|
| cue list | `{ "alts": [id, …], "random": true? }` | alternatives (§5.3); the game plays the first one whose conditions pass, or a random one if `random` |
| `if` / `show` / `select` | condition group (§6) | absent = no conditions |
| `once` | `"dialog"` \| `"always"` | ShowOnceCurrentDialog / ShowOnce; `"always"` wins if both are set |
| `actions` | `{ "<event>": [label, …] }` | English one-line descriptions, display only; the wording is not part of the format |
| `soulMark` | `{ "shift": { "dir", "value"? }, "requires": { "dir", "value"? , "rank"? } }` | `dir` is `Faith`, `Hope` or `Corruption`; a requirement has either `value` or `rank` |
| `comment` | string | designer note |
| `deleted` | `true` | shadow-deleted node |

### 5.2 Node kinds

Every node has `kind` plus the fields below. Fields not listed for a kind don't occur.

| `kind` | Fields |
|---|---|
| `cue` | `text`, `speaker`, `narrator`, `if`, `once`, `continue` (cue list), `answers` ([id]), `soulMark`, `actions.show`, `actions.stop` |
| `answers` | `answers` ([answer id]), `if`, `once`, `soulMark` (requires only) |
| `answer` | `text`, `next` (cue list), `show`, `select`, `once`, `tag`, `fakeTags`, `by`, `soulMark`, `actions.select`, `actions.success`, `actions.fail` |
| `check` | `tag`, `hidden`, `success` (id), `fail` (id), `if`, `once`, `actions.success`, `actions.fail` |
| `sequence` | `cues` ([id]), `exit` (id), `if`, `once` |
| `exit` | `answers` ([id]), `continue` (cue list) |
| `page` | `cues` ([id]), `answers` ([answer id]), `if`, `once`, `actions.show` |

* `text`: string key into `strings/<locale>.json`. Absent when the node has no text.
* `speaker`: internal speaker name (`AbelardCompanion`). Absent means an unknown speaker, shown as `NPC`.
  `narrator: true` marks narrator text and cues without a speaker.
* `tag`: skill check as displayed, e.g. `"Lore (Xenos), Hard"`. On answers it is the display-only check tag.
  `fakeTags` holds fake check tags.
* `by`: who answers or rolls: `Player`, `Companion` or `Random`. Absent means the default.

### 5.3 Flow

How the game plays a dialog, as the extractor understands it (DIALOG_STRUCTURE.md §3.2; partly inferred from data):

* **Cue list:** the game plays the first alternative whose conditions pass, or a random one if `random`.
* **Cue:** after the text, the game goes to `continue` if one of its alternatives passes. Otherwise it shows the first
  entry of `answers` that passes (usually an `answers` node). If neither exists, the dialog ends. A cue without
  `text` is a pass-through.
* **Answers:** every `answer` whose `show` passes is offered. `select` decides whether it can be clicked, and
  picking one follows `next`.
* **Check:** the game goes to `success` or `fail`.
* **Sequence:** each entry of `cues` plays in order, subject to its own `if`, then the flow goes to `exit`.
* **Exit:** works like the tail of a cue: `continue`, otherwise `answers`.
* **Page:** shows all `cues` as the page text, then offers `answers` directly.

The explorer does not simulate this. Wherever the game decides, the user chooses:

* **Alternatives:** the user picks from all options, each labeled with its conditions (and "random" where it
  applies). Options arise from:
  * a cue list with several alternatives;
  * `answers` with several entries;
  * a cue or exit with both `continue` and `answers`.
* **Fall-through:** when every alternative has conditions, the game may find none that passes. So the explorer also
  offers what happens then: the answers after a `continue`, and the end of the dialog otherwise. A conditional
  sequence entry becomes the choice between playing and skipping it.
* **Answers:** every answer is shown and clickable. `show` and `select` conditions appear as labels.
* **Checks:** the user picks success or failure.
* A step with a single, unconditional way forward proceeds automatically.

## 6. Conditions

### 6.1 Shape

```jsonc
// group: nested groups replace the game's OrAndLogic conditions
{ "op": "and" | "or", "not": true?, "items": [ <group or leaf>, … ] }

// leaf
{ "type": "CueSeen", "not": true?, "label": "not seen \"An excellent…\" in this conversation", …typed fields }
```

Every leaf has an English `label`, so the explorer can always display it. Leaves of the types in §6.2 also carry
typed fields for links and for later hints (§6.3). All other types (`EtudeStatus`, `QuestStatus`, `FlagInRange`,
`CheckConditionsHolder`, …) have only `type`, `not` and `label`. They refer to game data outside the export.

### 6.2 Typed leaves

| `type` | Fields | Hint source (later) |
|---|---|---|
| `CueSeen` | `node`, `dialog`, `text`, `scope` | path |
| `AnswerSelected` | `node`, `dialog`, `text`, `scope` | path |
| `AnswerListShown` | `node`, `dialog`, `scope` | path |
| `CheckPassed`, `CheckFailed` | `node`, `dialog` | path |
| `DialogSeen` | `dialog` | link only |
| `PcMale`, `PcFemale` | – | setting: gender |
| `CompanionInParty` | `companion`, `match` (subset of `active`, `detached`, `remote`, `ex`), `includeDead`? | setting: companions |
| `CompanionIsDead`, `CompanionIsLost` | `companion` | setting: companions |
| `CheckIsPlayerDominantSoulmark` | `dir` | setting: soul marks |
| `CurrentChapter` | `chapter` | setting: chapter |
| `False` | – | constant: never true |

* `node` / `dialog`: the referenced node and the dialog containing it (which may be another dialog). `dialog` is
  absent if the node isn't in the export.
* `text`: the referenced node's string key, so the explorer can show a snippet in the current locale.
* `scope: "dialog"`: the game's `CurrentDialog` flag ("in this conversation").

### 6.3 Display and state (guidance for the explorer)

* Conditions are labels. They never hide or block an option.
* The explorer tracks the current path: the nodes played and the choices made. A node with `once` that is already
  on the path is dimmed but can still be selected.
* `False` ("never") usually marks disabled content, which is worth a distinct badge.

**Later: hints.** The typed fields let the explorer evaluate conditions against the path and user settings. It could
then dim options the game wouldn't offer, but never block them.

* **Evaluation:** true, false or unknown. Anything that can't be evaluated is unknown.
* **From the path:**
  * `CueSeen`, `AnswerSelected`, `AnswerListShown`, `CheckPassed`, `CheckFailed` for nodes in the current dialog;
  * `once`.
* **From settings:**
  * gender: `PcMale`, `PcFemale`, and it also selects the `{mf|…}` text;
  * companion states: the `CompanionInParty` match states, `CompanionIsDead`, `CompanionIsLost`;
  * soul-mark points: the dominant direction and `requires` values;
  * chapter: `CurrentChapter`, defaulting to the dialog's `chapter`.
* **Inferred semantics:** these are not from game code.
  * The companion states `detached`, `remote` and `ex` are inferred from field names.
  * A soul-mark `value` is read as points.
  * `rank` thresholds aren't in the export.
  * `CurrentChapter` is read as equality.

## 7. `strings/<locale>.json`

```jsonc
{
  "locale": "deDE",
  "dialogs": { "<dialogId>": { "<key>": "text", … }, … },
  "fallback": ["<key>", …]              // keys whose text is the enGB fallback
}
```

* Grouping by dialog makes full-text search return the dialog directly. With the key, the explorer can find the
  node and a path to it from `start`.
* A string used by several dialogs appears once in each dialog's group.
* Texts keep the game's inline markup (DIALOG_STRUCTURE.md §5.5). The explorer renders it: `{n}` as narration,
  glossary links as plain text, `{mf|…}` as both variants (until a gender setting exists), and `{name}` as a
  placeholder.
* Keys that can't be resolved in any locale are absent. The explorer shows them as missing text.

## 8. Not included

* Banters and banter lists.
* Unreachable nodes.
* File paths of nodes, `parent`, voice-over ids, portraits, listener, animation, string metadata (traits, comments,
  source locale) and raw `extra` fields.
* The `dev` pseudo-locale, unless requested with `--locales`.
