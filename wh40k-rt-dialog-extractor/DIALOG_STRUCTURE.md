# Dialog data structure reference

Reference for the exported dialog data of *Warhammer 40,000: Rogue Trader* (base game + DLC1–3) in `data/`.
All figures below come from a full scan of the export (63,213 blueprint files, 54,032 string files, 0 parse errors).

---

## 1. Directory layout

The layout mirrors the game's own asset paths: `m_JsonPath` values are `Strings/Mechanics/<path>`, and
`<path>` matches the path under `data/Strings/` in 42,758 of 42,986 cases.

```
data/
├── Blueprints/
│   ├── World/Dialogs/          # base game
│   │   ├── Banters/            #   BlueprintBarkBanter  (ambient party banter, no Dialog wrapper)
│   │   ├── BantersList/        #   BlueprintBarkBanterList (weighted pools of banters)
│   │   ├── Ch0_Prologue/ … Ch5/#   story dialogs
│   │   ├── Companions/, Epilogues/, ExplorationEvents/, Misc/,
│   │   └── SoulMarksEvents/, TinyEpilogue/, TravelPrompts/, Test/
│   └── DLC/
│       └── DLC1/ DLC2/ DLC3/Narrative/…   # DLC dialogs
└── Strings/
    └── Blueprints/
        ├── World/Dialogs/      # 34,736 strings, mirrors Blueprints/World/Dialogs
        └── DLC/                # 19,296 strings: DLC1/, DLC2/, DLC3/ + a few loose DLC store strings
                                #   also contains the shared banter strings used by World/Dialogs/Banters
```

| Blueprints | Base game (`World`) | DLC1 | DLC2 | DLC3 |
|---|---:|---:|---:|---:|
| `BlueprintDialog` | 657 | 151 | 105 | 179 |
| `BlueprintCue` | 20,124 | 5,039 | 3,594 | 4,586 |
| `BlueprintAnswer` | 10,791 | 2,815 | 2,016 | 2,685 |
| String files | 34,736 | 7,244 | 5,507 | 6,523 |

* **One conversation = one leaf directory.** Each directory that contains a conversation holds exactly one
  `BlueprintDialog` (1,092 dirs) plus all of its node files (`Cue_*.jbp`, `Answer_*.jbp`, …).
  There are no directories with more than one dialog. This holds for the DLC too.
* Directories **without** a `BlueprintDialog`: banter / banter list folders, companion story folders, `*_Flag` folders,
  and a few DLC folders holding a single `BlueprintLoot` or `BlueprintColonyChronicle`.
* The tree depth varies. Do not assume a fixed depth. Find conversations by
  "directory containing a `BlueprintDialog`".
* **Strings are not always next to their blueprint.** Always resolve them through a global key index (§5.2).
  Examples:
  * base-game banters in `Blueprints/World/Dialogs/Banters` use shared strings from
    `Strings/Blueprints/DLC/DLC*/Narrative/Banters`
  * many dialogs use `Strings/Blueprints/World/Dialogs/CommonStrings/…`
* The strings tree also contains **folders with no blueprint counterpart** (`…/Barks`, `…/Items`, `…/Names`,
  `…/Quests`, `…/Colonization`, …). These hold strings owned by blueprints that are not part of this export.

### 1.1 Unique AssetIds

Every `AssetId` occurs in exactly one file. The loader should still **fail loudly on a duplicate AssetId**. An
accidental second copy of a folder would otherwise export every dialog twice, and the `AssetId → file` index
would silently point at whichever copy was read last.

### 1.2 File naming is NOT reliable

* **Always identify a blueprint by `Data.$type`, never by file name.** Typical names are `Cue_0001.jbp`,
  `Answer_12.jbp`, `AnswersList_0003.jbp`, `CueSequence_*.jbp`, `SequenceExit_*.jbp`, `Check_*.jbp`, `BookPage_*.jbp`,
  but there are many custom names (`Cogitator_Cue_3.jbp`, `Cass_Q2_answer.jbp`, `Cue_10_const .jbp`, …).
* The entry-point (`BlueprintDialog`) file name equals the directory name in only **181 of 657** base-game cases. Other
  names include `<Dir>_dialog.jbp`, `<Dir>_dialogue.jbp`, `<Dir>_prompt.jbp`, `<Something>_dialogue.jbp` in `<Dir>`, …
* File names can contain **spaces**, e.g. `NotDoneWithYou_dialog .jbp`, `Cue_0002 1.jbp`, `Idira _Kib.jbp`.
* Never derive the string file name from the blueprint file name. Link text **by key** (§5).

### 1.3 Encoding

All files are UTF‑8 JSON. Read them with `encoding="utf-8-sig"` to tolerate a BOM. On Windows set stdout to UTF‑8
when printing, because the text contains Cyrillic, CJK and typographic characters.

---

## 2. Blueprint file envelope (`.jbp`)

```jsonc
{
  "AssetId": "25ddc6b863634e5abd774b3c08972ce9",   // 32 hex chars, globally unique (no duplicates)
  "Data": {
    "$type": "c8ff73feae580b142a9f43e0c61d7f32, BlueprintDialog",  // "<type guid>, <TypeName>"
    "PrototypeLink": "", "m_Overrides": [], "Components": [],
    "Author": "…", "Comment": "…",
    "ParentAsset": "…",                             // most node types, see §3.9
    …type-specific fields…
  },
  "Meta": { "ShadowDeleted": false }               // may also be null (11 files)
}
```

### 2.1 References between blueprints

* A reference to another blueprint is a string **`"!bp_<AssetId>"`**. Strip the `!bp_` prefix and look the ID up in
  an `AssetId → file` index built over **all** of `data/Dialogs`.
* References to blueprints **outside the export** (units/speakers, etches, quests, flags, items, cutscenes, …) use
  the same syntax but won't resolve. That's expected: treat them as opaque IDs.
* `ParentAsset` is a bare AssetId (no `!bp_` prefix).
* Scene objects are referenced as `{ "EntityNameInEditor": …, "_entity_id": …, "SceneAssetGuid": … }`.
  They're unresolvable and irrelevant for text.

### 2.2 `ShadowDeleted`

`Meta.ShadowDeleted == true` marks an editor‑deleted asset: 1,308 files, including 22 whole dialogs
(e.g. folders named `*_ShadowDeleted`, `Dialogs/Test`). They are mostly unreachable, and most of the
unresolvable text keys come from them. Only 21 references from live assets point at shadow-deleted ones.
**Recommendation:** skip them by default and add an option to include them.

---

## 3. Node types

Counts are unique blueprints, base game + DLC.

| `$type` name               | Count  | Role |
|----------------------------|-------:|------|
| `BlueprintDialog`          |  1,092 | Entry point of a conversation |
| `BlueprintCue`             | 33,343 | One line spoken by an NPC / narrator |
| `BlueprintAnswer`          | 18,307 | One player reply option |
| `BlueprintAnswersList`     |  3,858 | A menu of player replies |
| `BlueprintCueSequence`     |  1,833 | Plays several cues in order, then an exit |
| `BlueprintSequenceExit`    |  1,814 | What happens after a `CueSequence` |
| `BlueprintCheck`           |  1,375 | Skill / attribute check that branches success/fail |
| `BlueprintBookPage`        |    618 | "Book event" page (illustrated narrative page with cues + answers) |
| `BlueprintBarkBanter`      |    819 | Standalone ambient banter (first phrase + responses), base game only |
| `BlueprintBarkBanterList`  |    104 | Weighted list of banters |
| `BlueprintCompanionStory`  |     13 | Companion biography entry (title + description) |
| `BlueprintColonyChronicle` |      5 | DLC3 colony chronicle: `m_BlueprintDialog` (ref to a Dialog), `m_Name`, `m_Description` |
| `BlueprintLoot`            |     26 | Loot container given via dialog action (no text) |
| `BlueprintUnlockableFlag`  |      6 | Story flag (no text) |

Quests, quest objectives, portraits and units are **not** in the export. About 1,200 condition/action references
point at DLC quests/objectives (`ObjectiveStatus`, `GiveObjective`, …) and portraits (`BookPage.Portrait`,
`Speaker.m_SpeakerPortrait`). They're external IDs like all other non-dialog references (§2.1).

### 3.1 Graph edges (structural links)

These are the only fields a traversal needs to follow. "Cue list" means the object
`{ "Cues": ["!bp_…", …], "Strategy": "First" | "Random" }`.

| From                    | Field                       | Targets (observed)                                          |
|-------------------------|-----------------------------|-------------------------------------------------------------|
| `BlueprintDialog`       | `FirstCue` (cue list)       | Cue, BookPage, CueSequence                                  |
| `BlueprintCue`          | `Answers` (array)           | **AnswersList** (normal), or Answer directly (256 cases)    |
| `BlueprintCue`          | `Continue` (cue list)       | Cue, CueSequence, Check                                     |
| `BlueprintAnswersList`  | `Answers` (array)           | Answer                                                      |
| `BlueprintAnswer`       | `NextCue` (cue list)        | Cue, Check, BookPage, CueSequence                           |
| `BlueprintCueSequence`  | `Cues` (array)              | Cue, BookPage, CueSequence (nested), Check                  |
| `BlueprintCueSequence`  | `m_Exit` (single ref)       | SequenceExit                                                |
| `BlueprintSequenceExit` | `Answers` (array)           | AnswersList (rarely Answer)                                 |
| `BlueprintSequenceExit` | `Continue` (cue list)       | Cue, CueSequence, Check                                     |
| `BlueprintCheck`        | `m_Success`, `m_Fail`       | Cue, BookPage, CueSequence                                  |
| `BlueprintBookPage`     | `Cues` (array)              | Cue, Check (the text shown on the page)                     |
| `BlueprintBookPage`     | `Answers` (array)           | Answer (**directly**, not via AnswersList)                  |
| `BlueprintBarkBanterList` | `m_BarkBanters` (array)   | BarkBanter                                                  |

Treat "cue list" targets generically: anything in a `Cues` list can be a Cue, CueSequence, Check or BookPage.
Dispatch on `$type`.

Observed properties of the graph:

* **Structural edges never leave the dialog's own directory.** Cross-directory references happen only inside
  conditions/actions (e.g. `DialogSeen`, `CueSeen` of another dialog).
* **The graph has cycles** (5,142 back edges in the base game alone), e.g. an answer that returns to an earlier answer list ("Ask about
  something else"). Nodes are also **shared**: ~2,040 cues and ~1,390 answer lists have more than one parent.
  A tree renderer must track visited nodes and emit "→ goto X" instead of recursing forever.
* 3 structural references point at missing assets (2 from shadow-deleted checks). Handle missing targets gracefully.
* In the base game ~1,450 node files are unreachable from their directory's `BlueprintDialog`. 1,134 of these are shadow-deleted;
  the rest are editor leftovers.

### 3.2 Conversation flow semantics

```
Dialog ──FirstCue──► Cue ──Answers──► AnswersList ──► Answer ──NextCue──► Cue …
                      │                                   │
                      └──Continue──► Cue / CueSequence / Check
```

* **Cue list resolution:** with `Strategy: "First"` (32,762 lists) the game plays the **first entry whose
  `Conditions` pass**. With `"Random"` (22 lists) it picks a random valid entry. So a multi-entry `Cues`
  list is a set of *alternatives*, not a sequence.
* **Cue → next:** after a cue is shown, **`Continue` takes precedence**: if one of its entries applies, the dialog
  goes there. Only otherwise does the player pick from the cue's `Answers` (the first AnswersList whose `Conditions`
  pass). If both are empty, **the dialog ends**. The data supports this: 1,727 live cues have both `Answers` and
  `Continue`. The continue chain almost always leads to companion interjections (a `CueSequence`) and ends with
  answers of its own, which are the *same* answer list as the cue's own in 1,472 cases. The designers mirror the
  answers onto the cue, and they only matter when every continue entry is conditional. `BlueprintSequenceExit`
  (`Answers` + `Continue`) is treated the same way. (This precedence is inferred from the data, not from game code.)
* **AnswersList:** all answers whose `ShowConditions` pass are shown. `SelectConditions` decides whether a shown
  answer is clickable.
* **CueSequence:** plays every entry of `Cues` in order (each still subject to its own conditions), then goes to
  `m_Exit` (a SequenceExit), which works like the tail end of a Cue (`Answers` or `Continue`).
* **Check:** runs a skill check (`Type`, `DC`, `Difficulty`, `DCModifiers`, `Hidden`) and jumps to
  `m_Success` or `m_Fail`. Actions `OnCheckSuccessActions` / `OnCheckFailActions`. `m_UnitEvaluator` can
  force which companion rolls.
* **BookPage:** shows all `Cues` as page text with an illustration (`ImageLink`, `BackgroundImageLink`, …), then
  offers `Answers` directly.

### 3.3 `BlueprintDialog` (entry point)

| Field | Meaning |
|---|---|
| `FirstCue` | cue list: where the conversation starts (often several alternatives with conditions) |
| `Conditions` | when the dialog may start |
| `StartActions`, `FinishActions`, `ReplaceActions` | action lists (`{ "Actions": [...] }`) |
| `Type` | `Common` (639), `Book` (13), `StarSystemEvent` (3), `Epilog` (2) |
| `TurnPlayer`, `TurnFirstSpeaker`, `IsNarratorText`, `IsLockCameraRotationButtons`, `StartPosition` | presentation |
| `OverrideCRForSkillChecks`, `OverridenCR` | (133 dialogs) challenge rating override |
| `Description` | localized text ref, almost always empty |

### 3.4 `BlueprintCue`

| Field | Meaning |
|---|---|
| `Text` | **localized text ref** (§5). Empty in 640 cues (pure logic / pass-through nodes) |
| `Speaker` | `{ m_Blueprint, m_SpeakerPortrait, NoSpeaker, MoveCamera, NotRevealInFoW, … }`, see §4 |
| `m_Listener` | unit the speaker addresses (external ref, rarely set) |
| `IsNarratorText` | narrator line |
| `Conditions` | must pass for the cue to be chosen from a cue list |
| `ShowOnce`, `ShowOnceCurrentDialog` | one-shot flags |
| `OnShow`, `OnStop` | action lists |
| `Answers` | array of AnswersList (or Answer) refs |
| `Continue` | cue list |
| `SoulMarkShift`, `SoulMarkRequirement`, `AlignmentShift` (22) | alignment data, see §3.8 |
| `Animation` | `None` or an animation name (`HeadNo`, `Bow`, …) |
| `Description` | localized ref, rarely used |

### 3.5 `BlueprintAnswer`

| Field | Meaning |
|---|---|
| `Text` | **localized text ref**. Empty in 313 answers |
| `NextCue` | cue list followed when the answer is picked |
| `ShowConditions` / `SelectConditions` | visibility / clickability |
| `ShowOnce`, `ShowOnceCurrentDialog` | hide after being chosen |
| `ShowCheck` | `{Type, Difficulty, DC}`: a **display-only** skill-check tag shown on the answer (`Type != "Unknown"` in 57 answers). The real check is usually the `BlueprintCheck` in `NextCue` |
| `FakeChecks` | list of `{Type, DC}` fake check tags (1 answer) |
| `CharacterSelection` | `{SelectionType: Clear/Player/Companion/Random, ComparisonStats}`: who answers / rolls |
| `OnSelect`, `OnCheckSuccess`, `OnCheckFail` | action lists |
| `SoulMarkShift`, `SoulMarkRequirement` | alignment gain / requirement (§3.8) |
| `AlignmentShift`, `AlignmentRequirement`, `MythicRequirement` | rare leftover fields (≤11 files) |
| `RequireValidCue`, `AddToHistory`, `DebugMode` | flags |
| `Components` | occasionally holds item/resource requirements |

### 3.6 `BlueprintAnswersList`

`Answers` (array of Answer refs), `Conditions`, `ShowOnce`, `SoulMarkRequirement`.

### 3.7 `BlueprintBarkBanter` / `BlueprintBarkBanterList`

Standalone and **not** reachable from any `BlueprintDialog`. Handle them as a separate top-level category.

```jsonc
{
  "m_Unit": "!bp_…",                         // who says FirstPhrase (external unit)
  "Conditions": { "ResponseRequired", "Unique", "MinChapter", "MaxChapter",
                  "ExtraConditions": { "Operation", "Conditions": [] } },
  "m_Weight": 1.0,
  "FirstPhrase": [ <localized ref>, … ],     // array of alternative opening lines
  "StrategySelectingResponse": "Random",
  "Responses": [ { "m_Unit": "!bp_…", "m_Weight": 0.0,
                   "Response": <localized ref>,
                   "ResponseCondition": { … } } ],
  "IsNotPartySpeaker": false                 // optional
}
```

`BlueprintBarkBanterList`: `{ "m_BarkBanters": ["!bp_…"], "m_Weight": … }`.

### 3.8 Soul marks (alignment)

`SoulMarkShift` / `SoulMarkRequirement` = `{ Direction, Value, CheckByRank, Rank, Description }`.

* `Direction`: `None`, `Faith` (Dogmatic), `Hope` (Iconoclast), `Corruption` (Heretic).
* `Value`: shift amount / required amount. It is often `0` for shifts, which presumably means the game's default
  amount.
* `Description`: localized ref, rarely filled.

### 3.9 `ParentAsset`

The editor's parent (the node that first created this one). It mirrors one incoming edge, but nodes can have
several parents, and it is empty or absent on ~960 nodes. **Use the forward edges (§3.1) for traversal**, and treat
`ParentAsset` only as a hint.

---

## 4. Speakers

* The export does **not** contain unit/character blueprints, so `Speaker.m_Blueprint` (e.g.
  `!bp_51604d37…` = Abelard) can't be resolved to a name from blueprints alone.
* **Use the string file's `speaker` field as the speaker name.** These are internal names such as `"Kunrad"`,
  `"AbelardCompanion"`, `"HeinrixCompanion"`, which is the naming the extractor keeps for now. In-game display
  names would need unit blueprints, which aren't exported.
* Build an `m_Blueprint → name` map from cues that have both a speaker blueprint and a string `speaker`. Use it for:
  * cues that only have `m_Blueprint` (69 live cues)
  * banter lines whose string has no `speaker` (338 of 2,078), via the banter's `m_Unit` / `Responses[].m_Unit`

  Only a handful of blueprints map to more than one name (e.g. `YrlietCompanion` / `YrlietQ1_Farseer01`); take the
  most frequent.
* Live cue speaker coverage (base game + DLC, live cues only):

  | Case | Cues |
  |---|---:|
  | `m_Blueprint` and string `speaker` | ~11,360 |
  | only string `speaker` | ~7,900 |
  | only `m_Blueprint` (use the map above) | 69 (4 blueprints have no name at all) |
  | neither | ~8,100 |
  | `Speaker.NoSpeaker == true` (narration / description, no speaker) | ~2,100 |

  For the "neither" case the game uses the dialog's *first speaker* at runtime: the NPC the player interacted with,
  which is defined in scene data, not in the dialog. Static options:
  * inherit the speaker of the nearest named cue in the same dialog (heuristic, can be wrong), or
  * print it as unknown/"NPC" (safe)
* **Answer strings never have a speaker.** Answers are always the player (or the companion chosen through
  `CharacterSelection`).
* Unnamed speaker blueprints (live):
  * `1c351398e24b4aebb2778ccdc39a4eed` (5 cues)
  * `88e6d28953574755b8eb960f646d6fd1` (3 cues)
  * `c08544dae8f040298b1044140d855cf9`
  * `48c7ce841c2a437b8c3b40b41ff0380a`
  * banter unit `287d7a4d2bb146998dc450cb3eccee78`

---

## 5. Localized text

### 5.1 Localized reference object (inside blueprints)

Every text field (`Cue.Text`, `Answer.Text`, `Description`s, banter phrases, …) has this shape:

```jsonc
{
  "m_Key": "db5d2764-b932-490e-864c-a9196703b725",     // string key (GUID with dashes)
  "m_OwnerString": "4cdc575e395b480ab894fa5ec3cd2b74",  // AssetId of the owning blueprint
  "m_OwnerPropertyPath": "Text",
  "m_JsonPath": "Strings/Mechanics/Blueprints\\World\\Dialogs\\Ch0_Prologue\\KunradIntroduction\\Cue_0002_Text.json",
  "Shared": null
}
```

There are three variants:

| Variant | Recognized by | Key to use | Count (Cue+Answer `Text`) |
|---|---|---|---|
| **Direct** (own string) | `m_Key != ""`, `Shared == null` | `m_Key` | 26,728 |
| **Shared** (reuses another string) | `Shared != null` | `Shared.stringkey` (`Shared.assetguid` = string asset GUID) | 3,097 |
| **Empty** | `m_Key == ""` and `Shared == null` | no text | 953 |

`m_JsonPath` is an editor path with mixed `\` and `/` separators. Normalize the separators and replace the
`Strings/Mechanics/` prefix with `Strings/`. The result then matches the actual string file path relative to
`data/` in 42,758 of 42,986 cases, **but it can be stale**. Use it only as a fallback.

### 5.2 Resolving a string: always by key

Build one global index `key → string file` over all of `data/Strings` (keys are unique: 34,736 keys, no
duplicates). Then:

```
key = ref.Shared.stringkey if ref.Shared else ref.m_Key
text = strings_by_key.get(key)
```

* **Shared strings often live in a different directory**, e.g. `Ch1/BridgeAndCabinet/Briefing/Answer_22.jbp`
  uses `Strings/Dialogs/Ch1/Voidship/HighFactotum/Answer_16_.Text_String.json`, and many use
  `Strings/Dialogs/CommonStrings/ZZ_CommonShareds/…`. The most reused string, `Answer_BE_continue_String.json`
  ("Continue."), is referenced by 389 blueprints.
* Consistency checks that hold:
  * direct refs: string `ownerGuid == m_OwnerString == blueprint AssetId` (100%)
  * shared refs: string `ownerGuid == Shared.assetguid` (100%)

**Resolution results for live (not shadow-deleted) dialog content, base game + DLC:**

| Where | Found | Missing |
|---|---:|---:|
| Cue/Answer `Text`, direct | 40,833 | 6 |
| Cue/Answer `Text`, shared | > 4,378 | 2 |
| BarkBanter phrases, direct | 1,089 | 0 |
| BarkBanter phrases, shared | 989 | 0 |
| Cue/Answer/Dialog `Description` (rarely used) | ~30 | ~215, mostly DLC1 |

The remaining gaps in live `Text`:

* `World/Dialogs/Ch2_VS/MawBreakthrough_BE/Cue_0004`, `Cue_2`: **`m_Key` contains literal Russian text instead of a
  GUID** (a data quirk). The string file at `m_JsonPath` exists and resolves correctly, so use it as the fallback.
* Single broken refs:
  * `World/Dialogs/Ch2_VS/UI_TestPolygon/TestUIDialog/Answer_15` (test dialog)
  * `World/Dialogs/TravelPrompts/Chapter2/MissingCrew_prompt/Cue_0010` (shared)
  * `DLC/DLC2/Narrative/FeudalWorld/FW_Moralite/Cue_145`
  * `DLC/DLC3/Narrative/Companion/CompanionQuest/Manipulus_Q2/TruthAboutNuncius/Answer_0036`, `Cue_0037`
  * `DLC/DLC3/Narrative/Medbay/MB_FinalAugmentatorMedbay/Answer_0009` (shared)

  These should be emitted as `<missing text: key>`.
* Shadow-deleted nodes account for most other misses (~400 refs, mostly DLC3). They're skipped by default anyway.

About 7,770 string files are not referenced by any dialog blueprint (barks, item names, quest text, colony events,
stale banter leftovers, …). This is expected.

### 5.3 String file naming (for orientation only)

| Pattern | Meaning |
|---|---|
| `<Blueprint>_Text.json` | direct `Text` of that blueprint (26,293 files) |
| `<Blueprint>_Text_1.json` | duplicate-name variant |
| `<Blueprint>_.Text_String.json`, `…_.Text_.json`, `<Name>_String.json` | **shared string assets** |
| `<Blueprint>_Description.json`, `<Blueprint>_SoulMarkShift.Description.json` | other localized properties |
| `<Banter>_FirstPhrase.Array.data[i].json`, `<Banter>_Responses.Array.data[i].Response.json` | banter phrases |
| `<Story>_Title.json`, `<Story>_Description.json` | companion story |

### 5.4 String file format

```jsonc
{
  "source": "ruRU",                         // original authoring locale (Russian)
  "key": "ca2ef6c0-f159-447d-96d3-164e4ab8bb84",   // matches m_Key / Shared.stringkey
  "ownerGuid": "57f325c6b885f0648b5e2c9e00e27a38", // owning blueprint AssetId / shared asset GUID (missing in 11)
  "speaker": "Kunrad",                      // optional (14,856 files)
  "speakerGender": "Male",                  // optional, alongside speaker
  "comment": "баркает пират",               // optional (1,135), writer note, usually Russian
  "string_traits": [ { "trait": "VO", "trait_date": "…", "locale_text": "" } ],
  "languages": [
    {
      "locale": "enGB",
      "text": "\"An excellent place for contemplation.\" {n}The man …{/n} …",
      "modification_date": "…",
      "translated_from": "ruRU",            // absent on the source locale
      "translation_date": "…",
      "original_text": "…",                 // source text at translation time
      "traits": [ { "trait": "Translated", "trait_date": "…", "locale_text": "…" } ]
    },
    …
  ]
}
```

* **Locales**: `enGB` (all), `deDE`, `frFR`, `esES` (all), `trTR`, `ruRU`, `jaJP`, `zhCN` (nearly all), `Sound`,
  `dev` (573).
  * `Sound` is **not a language**. Its `text` is the voice-over event name (e.g. `PRL_KunradIntroduction_01`),
    useful to mark voiced lines.
  * `dev` is a Russian developer draft.
* Look up a locale by the `locale` field. The array order is not guaranteed.
* `string_traits` / `traits` are localization workflow tags (`VO`, `DLC1`–`DLC3`, `Placeholder`, `Translated`,
  `CheckMe`, `AIGenerated`, many Russian-language pipeline labels). `DLCn` and `Placeholder` may be worth
  exporting; the rest can be ignored.

### 5.5 Inline markup in text

| Markup | Meaning | Plain-text rendering suggestion |
|---|---|---|
| `{n}…{/n}` | narrative / description (italic, not spoken) | keep contents, optionally wrap in `*…*` |
| `{g\|Encyclopedia:Key}…{/g}` | glossary link | keep inner text |
| `{d\|Encyclopedia:Key}…{/d}` | dynamic/decision glossary link | keep inner text |
| `{mf\|male\|female}` | gendered text by player sex | `male/female` or pick one |
| `{name}` | player character's name | e.g. `<Rogue Trader>` |
| `{petname}`, `{petName}` | romance pet name | placeholder |
| `{br}` | line break | `\n` |

---

## 6. Conditions and actions

Both are polymorphic objects identified by `$type` (`"<guid>, <Name>"`) plus a `name` like
`"$CueSeen$<guid>"`.

* **Condition container:** `{ "Operation": "And" | "Or", "Conditions": [ … ] }`. Each condition may carry
  `"Not": true`. `OrAndLogic` / `CheckConditionsHolder` nest further containers.
* **Action container:** `{ "Actions": [ … ] }`. `Conditional` actions contain `Conditions`, `IfTrue` and
  `IfFalse` blocks.
* Most common conditions:
  * `EtudeStatus` (4,073)
  * `CueSeen` (1,620, uses `m_Cue`)
  * `AnswerSelected` (1,290, uses `m_Answer`)
  * `CompanionInParty`
  * `ObjectiveStatus`, `QuestStatus`
  * `DialogSeen`
  * `FlagUnlocked`, `FlagInRange`, `FlagValue`
  * `CheckPassed` / `CheckFailed` (reference a `BlueprintCheck`)
  * `PcMale` / `PcFemale`
  * `ItemsEnough`, …
* Most common actions:
  * `StartEtude`, `PlayCutscene`
  * `SetObjectiveStatus`, `GiveObjective`
  * `IncrementFlagValue`, `UnlockFlag`
  * `Conditional`, `CompleteEtude`
  * `AddItemToPlayer`
  * `GainExp`, `GainPF` (profit factor), `GainFactionReputation`
  * `Recruit` / `Unrecruit`
  * `StartCombat`, `StartTrade`
* `CueSeen` / `AnswerSelected` / `DialogSeen` / `CheckPassed` point at blueprints in this export, sometimes in
  **other** dialogs. They can be rendered in human-readable form, e.g. `[if seen: Cue_0003 "…first words…"]`.
  Most other referenced blueprints (etudes, quests, flags, units, items) are external, so they can only be shown
  by type name + ID (or the `name` field).
* A few actions embed localized refs as well (e.g. bark text in `OnShow` / `OnStop`).

---

## 7. Worked example: `Blueprints/World/Dialogs/Ch0_Prologue/KunradIntroduction`

```
KunradIntroduction.jbp            BlueprintDialog  25ddc6b8…
  FirstCue.Cues ─► !bp_074a650d…  (Cue_0001.jbp)
Cue_0001.jbp                      BlueprintCue     074a650d…
  Text.Shared.stringkey ca2ef6c0-…  ─► Strings/…/KunradIntroduction/Cue_0001_.Text_String.json
                                        speaker "Kunrad", enGB "\"An excellent place for contemplation.\" …"
  Answers ─► !bp_a4c3a8ce…        (AnswersList_0001.jbp)
AnswersList_0001.jbp              BlueprintAnswersList
  Answers ─► 5 × Answer (…07e92e80, 813d20bc, 18e256c9, c0c7e6d1, eaa51933)
Answer_0001.jbp                   BlueprintAnswer  07e92e80…
  Text ─► string 33dc0339-…       NextCue.Cues ─► !bp_6b147b8c… (a Cue) …
```

---

## 8. Recommended extraction algorithm

1. **Index** all `data/Blueprints/**/*.jbp` → `AssetId → (path, blueprint)`, erroring on duplicate AssetIds (§1.1).
   Index all `data/Strings/**/*.json` → `key → string`. Loading all ~117k files takes several minutes on this machine
   (slow filesystem), so cache the parsed index, e.g. as a pickle keyed by file mtimes.
2. **Find roots:** every `BlueprintDialog` (skip `ShadowDeleted` unless requested). Handle `BlueprintBarkBanter`
   (+ lists), `BlueprintCompanionStory`, `BlueprintColonyChronicle` as separate categories. Group output by
   source (`World`, `DLC1`, `DLC2`, `DLC3`) and directory.
3. **Traverse** each dialog from `FirstCue` using only the edges in §3.1, dispatching on `$type`. Track visited
   nodes; on revisit emit a link/goto instead of re-expanding (cycles and shared nodes).
4. **Resolve text** via the key index (`Shared.stringkey` or `m_Key`), falling back to `m_JsonPath` (normalized as
   in §5.1; also covers the `m_Key`-contains-literal-text quirk). Choose a
   locale (default `enGB`). Record `Sound` for VO.
5. **Resolve speaker** from the string's `speaker`, then the `m_Blueprint → name` map, then "unknown / first
   speaker". Answers are the player.
6. **Summarize conditions / actions** by `$type` name, `Not`, and resolvable in-export references.
7. **Emit:**
   * JSON: a node map keyed by AssetId with typed edges. This keeps cycles lossless.
   * TXT: an indented tree with goto markers, e.g.

     ```
     [Kunrad] "An excellent place…"
       1. "Answer text"  [Lore (Imperium) DC 55] {if: not AnswerSelected(…)}
          [Kunrad] "…"
       2. …
     ```
