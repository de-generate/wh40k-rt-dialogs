"""Parse the raw export (``data/Blueprints`` + ``data/Strings``) into a DialogDatabase.

See DIALOG_STRUCTURE.md for a description of the input format.
"""

from __future__ import annotations

import collections
import dataclasses
import datetime
import hashlib
import json
import os
import posixpath
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Iterable

from . import serialize
from .model import (
    Action,
    Answer,
    AnswersList,
    Banter,
    BanterList,
    BanterResponse,
    BookPage,
    Check,
    Condition,
    ConditionGroup,
    Cue,
    CueList,
    CueSequence,
    Dialog,
    DialogDatabase,
    LocalizedString,
    NodeType,
    SequenceExit,
    SkillCheck,
    SoulMark,
    Speaker,
    node_children,
)

Progress = Callable[[str], None]

BLUEPRINTS_DIR = "Blueprints"
STRINGS_DIR = "Strings"

# Raw fields that carry no useful information for dialog extraction.
IGNORED_FIELDS = {
    "$type",
    "PrototypeLink",
    "m_Overrides",
    "Author",
    "ParentAsset",
    "Comment",
    "m_EditorComment",
}
# Raw fields that are left out of ``extra`` when they have their usual value.
USUAL_VALUES = {
    "AddToHistory": True,
    "TurnSpeaker": True,
    "TurnPlayer": True,
    "TurnFirstSpeaker": True,
}

NODE_TYPES = {
    "BlueprintCue": "Cue",
    "BlueprintAnswer": "Answer",
    "BlueprintAnswersList": "AnswersList",
    "BlueprintCueSequence": "CueSequence",
    "BlueprintSequenceExit": "SequenceExit",
    "BlueprintCheck": "Check",
    "BlueprintBookPage": "BookPage",
}


class ExportError(Exception):
    pass


# ------------------------------------------------------------------ file access


def list_files(root: Path, sub: str, suffix: str) -> list[tuple[str, int, int]]:
    """(path relative to ``root``, size, mtime_ns) of every ``*suffix`` file below root/sub."""
    out = []
    stack = [root / sub]
    while stack:
        with os.scandir(stack.pop()) as it:
            for e in it:
                if e.is_dir():
                    stack.append(Path(e.path))
                elif e.name.lower().endswith(suffix):
                    st = e.stat()
                    out.append(
                        (
                            Path(e.path).relative_to(root).as_posix(),
                            st.st_size,
                            st.st_mtime_ns,
                        )
                    )
    out.sort()
    return out


def fingerprint(files: Iterable[tuple[str, int, int]]) -> str:
    """Cheap change detector for the input files (paths, sizes and mtimes)."""
    h = hashlib.sha1()
    for rel, size, mtime in files:
        h.update(f"{rel}\0{size}\0{mtime}\n".encode())
    return h.hexdigest()


def source_fingerprint(data_root: Path) -> str:
    data_root = Path(data_root)
    return fingerprint(
        list_files(data_root, BLUEPRINTS_DIR, ".jbp")
        + list_files(data_root, STRINGS_DIR, ".json")
    )


def read_json_files(
    root: Path, rels: list[str], workers: int, progress: Progress, label: str
) -> tuple[dict[str, Any], list[str]]:
    def read(rel: str):
        try:
            with open(root / rel, encoding="utf-8-sig") as fh:
                return rel, json.load(fh), None
        except Exception as e:  # report and continue
            return rel, None, f"cannot parse {rel}: {e}"

    out, errors = {}, []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for i, (rel, data, err) in enumerate(pool.map(read, rels, chunksize=64), 1):
            if err:
                errors.append(err)
            else:
                out[rel] = data
            if i % 10000 == 0 or i == len(rels):
                progress(f"{label}: {i}/{len(rels)}")
    return out, errors


# ------------------------------------------------------------------ helpers


def short_type(t: str) -> str:
    """'8eee9d…, BlueprintCue' -> 'BlueprintCue'."""
    return t.rsplit(", ", 1)[-1]


def ref(v: Any) -> str | None:
    if isinstance(v, str) and v.startswith("!bp_"):
        return v[4:] or None
    return v or None


def refs(vs: Any) -> list[str]:
    return [r for r in (ref(v) for v in vs or []) if r]


def source_of(rel: str) -> str:
    parts = rel.split("/")
    if len(parts) > 2 and parts[1] == "World":
        return "World"
    if len(parts) > 3 and parts[1] == "DLC":
        return parts[2]
    return parts[1] if len(parts) > 1 else ""


def is_deleted(bp: dict) -> bool:
    return bool((bp.get("Meta") or {}).get("ShadowDeleted"))


def _empty(v: Any) -> bool:
    return v is None or v == "" or v == [] or v == {}


class _Fields:
    """Tracks which raw fields were consumed so the rest can go to ``extra``."""

    def __init__(self, data: dict):
        self.data = data
        self.used: set[str] = set()

    def __call__(self, key: str, default: Any = None) -> Any:
        self.used.add(key)
        v = self.data.get(key)
        return default if v is None else v

    def rest(self) -> dict[str, Any]:
        return {
            k: v
            for k, v in self.data.items()
            if k not in self.used and k not in IGNORED_FIELDS
        }


# ------------------------------------------------------------------ builder


class _Builder:
    def __init__(
        self, blueprints: dict[str, dict], strings: dict[str, dict], progress: Progress
    ):
        self.progress = progress
        self.issues: list[str] = []
        self.blueprints = blueprints
        self.strings = strings
        self.string_by_key: dict[str, str] = {}
        for rel, s in strings.items():
            k = s.get("key")
            if not k:
                self.issues.append(f"string file without key: {rel}")
            elif k in self.string_by_key:
                self.issues.append(
                    f"duplicate string key {k}: {self.string_by_key[k]} and {rel}"
                )
            else:
                self.string_by_key[k] = rel
        self._string_cache: dict[str, LocalizedString] = {}
        self.locales: set[str] = set()

        self.by_id: dict[str, str] = {}
        dups = []
        for rel, bp in blueprints.items():
            aid = bp.get("AssetId") if isinstance(bp, dict) else None
            if not aid or not isinstance(bp.get("Data"), dict):
                self.issues.append(f"not a blueprint: {rel}")
                continue
            if aid in self.by_id:
                dups.append(f"{aid}: {self.by_id[aid]} and {rel}")
            self.by_id[aid] = rel
        if dups:
            raise ExportError(
                f"{len(dups)} duplicate AssetIds (duplicated folder?), e.g.\n  "
                + "\n  ".join(dups[:5])
            )
        self.speakers: dict[str, str] = {}
        self._context = ""  # blueprint currently being parsed (for issue messages)

    # -------------------------------------------------------------- strings

    def _load_string(self, rel: str) -> LocalizedString:
        s = self.strings[rel]
        texts, voice = {}, None
        for lang in s.get("languages") or []:
            loc, text = lang.get("locale"), lang.get("text")
            if loc == "Sound":
                voice = text or None
            elif loc:
                texts[loc] = text or ""
        self.locales.update(texts)
        return LocalizedString(
            key=s["key"],
            texts=texts,
            voice_over=voice,
            speaker=s.get("speaker") or None,
            speaker_gender=s.get("speakerGender") or None,
            comment=s.get("comment") or None,
            source_locale=s.get("source") or None,
            traits=[t["trait"] for t in s.get("string_traits") or [] if t.get("trait")],
            path=rel,
        )

    def _string_at(self, rel: str) -> LocalizedString:
        ls = self._string_cache.get(rel)
        if ls is None:
            ls = self._string_cache[rel] = self._load_string(rel)
        return ls

    def text(self, raw: Any, where: str) -> LocalizedString | None:
        """Resolve a localized reference ``{m_Key, Shared, m_JsonPath, …}``."""
        if not isinstance(raw, dict):
            return None
        shared = raw.get("Shared") or None
        key = (
            (shared or {}).get("stringkey")
            or (None if shared else raw.get("m_Key"))
            or None
        )
        if not key:
            return None
        rel = self.string_by_key.get(key)
        if rel is None and raw.get("m_JsonPath"):
            jp = raw["m_JsonPath"].replace("\\", "/")
            if jp.startswith("Strings/Mechanics/"):
                jp = STRINGS_DIR + "/" + jp[len("Strings/Mechanics/") :]
            if jp in self.strings:
                rel = jp
        if rel is None:
            self.issues.append(f"missing string {key!r} for {where} in {self._context}")
            return LocalizedString(key=key, shared=bool(shared), missing=True)
        ls = self._string_at(rel)
        return dataclasses.replace(ls, shared=True) if shared else ls

    # ------------------------------------------------------ generic values

    def clean(self, v: Any) -> Any:
        """Raw game data -> compact JSON: short ``$type``, no editor ``name``, no empty values,
        localized references resolved to ``{"$localized": <LocalizedString>}``."""
        if isinstance(v, dict):
            if "m_Key" in v and "Shared" in v:
                ls = self.text(v, "embedded text")
                return {"$localized": serialize.to_json(ls)} if ls else None
            out = {}
            for k, x in v.items():
                if k == "$type":
                    out[k] = short_type(x)
                elif k == "name" and isinstance(x, str) and x.startswith("$"):
                    continue
                else:
                    x = self.clean(x)
                    if not _empty(x):
                        out[k] = x
            return out
        if isinstance(v, list):
            return [self.clean(x) for x in v]
        return v

    def extra(self, f: _Fields) -> dict[str, Any]:
        out = {}
        for k, v in f.rest().items():
            if v is False or USUAL_VALUES.get(k, object()) == v:
                continue
            v = self.clean(v)
            if not _empty(v):
                out[k] = v
        return out

    def conditions(self, raw: Any) -> ConditionGroup:
        if not isinstance(raw, dict):
            return ConditionGroup()
        out = []
        for c in raw.get("Conditions") or []:
            params = self.clean(
                {k: v for k, v in c.items() if k not in ("$type", "Not")}
            )
            out.append(
                Condition(
                    type=short_type(c.get("$type", "?")),
                    negated=bool(c.get("Not")),
                    params=params,
                )
            )
        return ConditionGroup(operation=raw.get("Operation") or "And", conditions=out)

    def actions(self, raw: Any) -> list[Action]:
        if not isinstance(raw, dict):
            return []
        return [
            Action(
                type=short_type(a.get("$type", "?")),
                params=self.clean({k: v for k, v in a.items() if k != "$type"}),
            )
            for a in raw.get("Actions") or []
        ]

    @staticmethod
    def cue_list(raw: Any) -> CueList:
        if not isinstance(raw, dict):
            return CueList()
        return CueList(
            cues=refs(raw.get("Cues")), strategy=raw.get("Strategy") or "First"
        )

    def soul_mark(self, raw: Any, where: str) -> SoulMark | None:
        if not isinstance(raw, dict) or raw.get("Direction", "None") == "None":
            return None
        return SoulMark(
            direction=raw["Direction"],
            value=raw.get("Value") or 0,
            check_by_rank=bool(raw.get("CheckByRank")),
            rank=raw.get("Rank") or 0,
            description=self.text(raw.get("Description"), where + ".Description"),
        )

    # ------------------------------------------------------------ speakers

    def build_speaker_map(self) -> None:
        """unit blueprint id -> most frequent internal speaker name found in strings."""
        names: dict[str, collections.Counter] = collections.defaultdict(
            collections.Counter
        )

        def note(unit: Any, text_ref: Any) -> None:
            unit = ref(unit)
            if not unit or not isinstance(text_ref, dict):
                return
            shared = text_ref.get("Shared") or {}
            rel = self.string_by_key.get(
                shared.get("stringkey") or text_ref.get("m_Key") or ""
            )
            name = self.strings[rel].get("speaker") if rel else None
            if name:
                names[unit][name] += 1

        for bp in self.blueprints.values():
            d = bp["Data"]
            t = short_type(d.get("$type", ""))
            if t == "BlueprintCue":
                note((d.get("Speaker") or {}).get("m_Blueprint"), d.get("Text"))
            elif t == "BlueprintBarkBanter":
                for p in d.get("FirstPhrase") or []:
                    note(d.get("m_Unit"), p)
                for r in d.get("Responses") or []:
                    note(r.get("m_Unit"), r.get("Response"))
        self.speakers = {u: c.most_common(1)[0][0] for u, c in sorted(names.items())}

    def speaker_name(
        self, unit: str | None, text: LocalizedString | None
    ) -> tuple[str | None, str | None]:
        if text and text.speaker:
            return text.speaker, "string"
        if unit and unit in self.speakers:
            return self.speakers[unit], "blueprint"
        return None, None

    # --------------------------------------------------------------- nodes

    def node(self, rel: str, bp: dict) -> NodeType:
        d = bp["Data"]
        f = _Fields(d)
        kind = NODE_TYPES[short_type(d["$type"])]
        common = dict(
            id=bp["AssetId"],
            path=rel,
            parent=d.get("ParentAsset") or None,
            comment=d.get("Comment") or None,
            deleted=is_deleted(bp),
        )
        if kind == "Cue":
            text = self.text(f("Text"), "Text")
            sp = f("Speaker", {})
            unit = ref(sp.get("m_Blueprint"))
            name, name_source = self.speaker_name(unit, text)
            node = Cue(
                **common,
                text=text,
                speaker=Speaker(
                    blueprint=unit,
                    name=name,
                    name_source=name_source,
                    no_speaker=bool(sp.get("NoSpeaker")),
                    portrait=ref(sp.get("m_SpeakerPortrait")),
                ),
                listener=ref(f("m_Listener")),
                narrator=bool(f("IsNarratorText")),
                animation=None if f("Animation", "None") == "None" else d["Animation"],
                conditions=self.conditions(f("Conditions")),
                show_once=bool(f("ShowOnce")),
                show_once_current_dialog=bool(f("ShowOnceCurrentDialog")),
                on_show=self.actions(f("OnShow")),
                on_stop=self.actions(f("OnStop")),
                answers=refs(f("Answers")),
                continue_cues=self.cue_list(f("Continue")),
                soul_mark_shift=self.soul_mark(f("SoulMarkShift"), "SoulMarkShift"),
                soul_mark_requirement=self.soul_mark(
                    f("SoulMarkRequirement"), "SoulMarkRequirement"
                ),
                description=self.text(f("Description"), "Description"),
            )
        elif kind == "Answer":
            check = f("ShowCheck", {})
            cs = f("CharacterSelection", {})
            node = Answer(
                **common,
                text=self.text(f("Text"), "Text"),
                next_cues=self.cue_list(f("NextCue")),
                show_conditions=self.conditions(f("ShowConditions")),
                select_conditions=self.conditions(f("SelectConditions")),
                show_once=bool(f("ShowOnce")),
                show_once_current_dialog=bool(f("ShowOnceCurrentDialog")),
                skill_check=None
                if check.get("Type", "Unknown") == "Unknown"
                else SkillCheck(
                    type=check["Type"],
                    difficulty=check.get("Difficulty"),
                    dc=check.get("DC") or 0,
                ),
                fake_checks=[
                    SkillCheck(
                        type=c.get("Type", "?"),
                        difficulty=c.get("Difficulty"),
                        dc=c.get("DC") or 0,
                    )
                    for c in f("FakeChecks", [])
                ],
                character_selection=None
                if cs.get("SelectionType", "Clear") == "Clear"
                else cs["SelectionType"],
                on_select=self.actions(f("OnSelect")),
                on_check_success=self.actions(f("OnCheckSuccess")),
                on_check_fail=self.actions(f("OnCheckFail")),
                soul_mark_shift=self.soul_mark(f("SoulMarkShift"), "SoulMarkShift"),
                soul_mark_requirement=self.soul_mark(
                    f("SoulMarkRequirement"), "SoulMarkRequirement"
                ),
                description=self.text(f("Description"), "Description"),
            )
            if cs.get("ComparisonStats"):
                node.extra["CharacterSelection.ComparisonStats"] = self.clean(
                    cs["ComparisonStats"]
                )
        elif kind == "AnswersList":
            node = AnswersList(
                **common,
                answers=refs(f("Answers")),
                conditions=self.conditions(f("Conditions")),
                show_once=bool(f("ShowOnce")),
                soul_mark_requirement=self.soul_mark(
                    f("SoulMarkRequirement"), "SoulMarkRequirement"
                ),
            )
        elif kind == "CueSequence":
            node = CueSequence(
                **common,
                cues=refs(f("Cues")),
                exit=ref(f("m_Exit")),
                conditions=self.conditions(f("Conditions")),
                show_once=bool(f("ShowOnce")),
                show_once_current_dialog=bool(f("ShowOnceCurrentDialog")),
            )
        elif kind == "SequenceExit":
            node = SequenceExit(
                **common,
                answers=refs(f("Answers")),
                continue_cues=self.cue_list(f("Continue")),
            )
        elif kind == "Check":
            node = Check(
                **common,
                skill=f("Type"),
                difficulty=f("Difficulty"),
                dc=f("DC", 0),
                hidden=bool(f("Hidden")),
                success=ref(f("m_Success")),
                fail=ref(f("m_Fail")),
                conditions=self.conditions(f("Conditions")),
                on_success=self.actions(f("OnCheckSuccessActions")),
                on_fail=self.actions(f("OnCheckFailActions")),
                show_once=bool(f("ShowOnce")),
                show_once_current_dialog=bool(f("ShowOnceCurrentDialog")),
            )
        else:  # BookPage
            node = BookPage(
                **common,
                cues=refs(f("Cues")),
                answers=refs(f("Answers")),
                conditions=self.conditions(f("Conditions")),
                on_show=self.actions(f("OnShow")),
                show_once=bool(f("ShowOnce")),
                show_once_current_dialog=bool(f("ShowOnceCurrentDialog")),
            )
        node.extra.update(self.extra(f))
        return node

    def dialog(self, rel: str, bp: dict) -> Dialog:
        d = bp["Data"]
        f = _Fields(d)
        dialog = Dialog(
            id=bp["AssetId"],
            name=posixpath.splitext(posixpath.basename(rel))[0],
            path=rel,
            source=source_of(rel),
            type=f("Type", "Common"),
            comment=d.get("Comment") or None,
            deleted=is_deleted(bp),
            first_cue=self.cue_list(f("FirstCue")),
            conditions=self.conditions(f("Conditions")),
            start_actions=self.actions(f("StartActions")),
            finish_actions=self.actions(f("FinishActions")),
            replace_actions=self.actions(f("ReplaceActions")),
            description=self.text(f("Description"), "Description"),
        )
        dialog.extra = self.extra(f)
        return dialog

    def banter(self, rel: str, bp: dict) -> Banter:
        d = bp["Data"]
        f = _Fields(d)
        cond = f("Conditions", {})
        unit = ref(f("m_Unit"))
        phrases = [
            t for t in (self.text(p, "FirstPhrase") for p in f("FirstPhrase", [])) if t
        ]
        responses = []
        for r in f("Responses", []):
            r_unit = ref(r.get("m_Unit"))
            r_text = self.text(r.get("Response"), "Response")
            responses.append(
                BanterResponse(
                    unit=r_unit,
                    speaker=self.speaker_name(r_unit, r_text)[0],
                    weight=float(r.get("m_Weight") or 0),
                    text=r_text,
                    conditions=self.conditions(r.get("ResponseCondition")),
                )
            )
        banter = Banter(
            id=bp["AssetId"],
            name=posixpath.splitext(posixpath.basename(rel))[0],
            path=rel,
            source=source_of(rel),
            comment=d.get("Comment") or None,
            deleted=is_deleted(bp),
            unit=unit,
            speaker=self.speaker_name(unit, phrases[0] if phrases else None)[0],
            weight=float(f("m_Weight", 0)),
            response_required=bool(cond.get("ResponseRequired")),
            unique=bool(cond.get("Unique")),
            min_chapter=cond.get("MinChapter") or 0,
            max_chapter=cond.get("MaxChapter") or 0,
            conditions=self.conditions(cond.get("ExtraConditions")),
            first_phrases=phrases,
            response_strategy=f("StrategySelectingResponse"),
            responses=responses,
        )
        banter.extra = self.extra(f)
        return banter

    # --------------------------------------------------------------- build

    def build(self) -> DialogDatabase:
        self.build_speaker_map()
        by_dir: dict[str, list[tuple[str, dict]]] = collections.defaultdict(list)
        dialogs, banters, banter_lists = [], [], []
        skipped = collections.Counter()
        valid = set(self.by_id.values())
        for rel, bp in sorted(self.blueprints.items()):
            if rel not in valid:
                continue  # not a blueprint (reported above)
            t = short_type(bp["Data"].get("$type", ""))
            self._context = rel
            if t in NODE_TYPES or t == "BlueprintDialog":
                by_dir[posixpath.dirname(rel)].append((rel, bp))
            elif t == "BlueprintBarkBanter":
                banters.append(self.banter(rel, bp))
            elif t == "BlueprintBarkBanterList":
                d = bp["Data"]
                banter_lists.append(
                    BanterList(
                        id=bp["AssetId"],
                        name=posixpath.splitext(posixpath.basename(rel))[0],
                        path=rel,
                        source=source_of(rel),
                        deleted=is_deleted(bp),
                        weight=float(d.get("m_Weight") or 0),
                        banters=refs(d.get("m_BarkBanters")),
                    )
                )
            else:
                skipped[t] += 1
        if skipped:
            self.progress(
                "not part of the dialog database: "
                + ", ".join(f"{t} ({n})" for t, n in skipped.most_common())
            )

        for directory, items in sorted(by_dir.items()):
            roots = [
                (rel, bp)
                for rel, bp in items
                if short_type(bp["Data"]["$type"]) == "BlueprintDialog"
            ]
            if not roots:
                self.issues.append(
                    f"{len(items)} dialog nodes without a BlueprintDialog in {directory}"
                )
                continue
            if len(roots) > 1:
                self.issues.append(
                    f"{len(roots)} BlueprintDialogs in {directory}; nodes assigned to the first"
                )
            self._context = roots[0][0]
            dialog = self.dialog(*roots[0])
            for rel, bp in roots[1:]:
                self._context = rel
                dialogs.append(self.dialog(rel, bp))
            for rel, bp in items:
                if short_type(bp["Data"]["$type"]) != "BlueprintDialog":
                    self._context = rel
                    dialog.nodes[bp["AssetId"]] = self.node(rel, bp)
            self.mark_reachable(dialog)
            dialogs.append(dialog)
        self._context = ""

        return DialogDatabase(
            generated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(
                timespec="seconds"
            ),
            locales=sorted(self.locales),
            speakers=self.speakers,
            dialogs=sorted(dialogs, key=lambda x: x.path),
            banters=banters,
            banter_lists=banter_lists,
            issues=self.issues,
        )

    def mark_reachable(self, dialog: Dialog) -> None:
        seen: set[str] = set()
        stack = list(dialog.first_cue.cues)
        for target in stack:
            self._check_target(dialog, dialog.path, target)
        while stack:
            nid = stack.pop()
            if nid in seen or nid not in dialog.nodes:
                continue
            seen.add(nid)
            node = dialog.nodes[nid]
            for child in node_children(node):
                self._check_target(dialog, node.path, child)
                stack.append(child)
        for nid, node in dialog.nodes.items():
            node.reachable = nid in seen

    def _check_target(self, dialog: Dialog, src: str, target: str) -> None:
        if target in dialog.nodes:
            return
        where = self.by_id.get(target)
        if where is None:
            self.issues.append(f"missing blueprint {target} referenced by {src}")
        else:
            self.issues.append(f"{src} links to {where} outside its dialog directory")


# ------------------------------------------------------------------ entry point


def parse_export(
    data_root: str | os.PathLike, workers: int = 16, progress: Progress = lambda s: None
) -> DialogDatabase:
    """Read every blueprint and string file below ``data_root`` and build the database."""
    data_root = Path(data_root)
    for sub in (BLUEPRINTS_DIR, STRINGS_DIR):
        if not (data_root / sub).is_dir():
            raise ExportError(f"{data_root / sub} does not exist")
    bp_files = list_files(data_root, BLUEPRINTS_DIR, ".jbp")
    str_files = list_files(data_root, STRINGS_DIR, ".json")
    progress(f"found {len(bp_files)} blueprint and {len(str_files)} string files")
    blueprints, e1 = read_json_files(
        data_root, [f[0] for f in bp_files], workers, progress, "blueprints"
    )
    strings, e2 = read_json_files(
        data_root, [f[0] for f in str_files], workers, progress, "strings"
    )
    builder = _Builder(blueprints, strings, progress)
    builder.issues[:0] = e1 + e2
    db = builder.build()
    db.data_root = str(data_root)
    db.source_fingerprint = fingerprint(bp_files + str_files)
    return db
