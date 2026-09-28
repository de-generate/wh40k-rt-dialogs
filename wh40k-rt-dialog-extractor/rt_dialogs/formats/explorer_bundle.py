"""Explorer bundle: the compact zip the dialog explorer loads.

The format is specified in EXPLORER_BUNDLE.md; keep both in sync and bump ``VERSION`` on
changes the explorer must know about.
"""

from __future__ import annotations

import argparse
import collections
import json
import re
import sys
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..describe import FALLBACK_LOCALE, Describer, check_tag
from ..model import (
    Action,
    Answer,
    AnswersList,
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
    SoulMark,
)
from .common import add_dialog_selection, select_dialogs

FORMAT = "rt-dialogs-explorer-bundle"
VERSION = 1

_CHAPTER = re.compile(r"^Ch(?:apter)?_?(\d+)(?:_|$)")
# condition type -> param holding the referenced node
_NODE_REFS = {
    "CueSeen": "m_Cue",
    "AnswerSelected": "m_Answer",
    "AnswerListShown": "m_AnswersList",
    "CheckPassed": "m_Check",
    "CheckFailed": "m_Check",
}
_COMPANION_STATES = {
    "MatchWhenActive": "active",
    "MatchWhenDetached": "detached",
    "MatchWhenRemote": "remote",
    "MatchWhenEx": "ex",
}


def _compact(d: dict[str, Any]) -> dict[str, Any]:
    """Drop optional fields that have their default value (0 is a real value and stays)."""
    return {
        k: v
        for k, v in d.items()
        if not (v is None or v is False or v == "" or v == [] or v == {})
    }


def _bp(v: Any) -> str | None:
    return v[4:] or None if isinstance(v, str) and v.startswith("!bp_") else None


def _key(ls: LocalizedString | None) -> str | None:
    return ls.key if ls else None


def _once(node: NodeType) -> str | None:
    if getattr(node, "show_once", False):
        return "always"
    if getattr(node, "show_once_current_dialog", False):
        return "dialog"
    return None


def dialog_tags(path: str, name: str) -> list[str]:
    """``World/Dialogs/Ch1/Voidship/Foo`` -> ``["Ch1", "Voidship"]`` (for dialog ``Foo``)."""
    parts = path.split("/")
    if parts[:2] == ["World", "Dialogs"]:
        parts = parts[2:]
    elif parts[:1] == ["DLC"]:
        parts = parts[1:]
    parts = [p for p in parts if p != "Narrative"]
    if parts and parts[-1] == name:
        parts.pop()
    return parts


def dialog_chapter(tags: list[str]) -> int | None:
    for t in tags:
        m = _CHAPTER.match(t)
        if m:
            return int(m.group(1))
    return None


def _dumps(obj: Any) -> bytes:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


class BundleBuilder:
    def __init__(self, db: DialogDatabase, dialogs: list[Dialog], locales: list[str]):
        self.db = db
        self.dialogs = dialogs
        self.locales = locales
        self.desc = Describer(db, FALLBACK_LOCALE)  # labels are English
        self.all_dialogs = {d.id for d in db.dialogs}
        self.companions: set[str] = set()

    @staticmethod
    def included(dialog: Dialog) -> list[NodeType]:
        return [n for n in dialog.nodes.values() if n.reachable]

    # ------------------------------------------------------------ building blocks

    @staticmethod
    def cue_list(cl: CueList) -> dict | None:
        if not cl.cues:
            return None
        return _compact({"alts": list(cl.cues), "random": cl.strategy == "Random"})

    def actions(self, **events: list[Action]) -> dict | None:
        out = {k: [self.desc.action(a) for a in v] for k, v in events.items() if v}
        return out or None

    @staticmethod
    def soul_mark(shift: SoulMark | None, requires: SoulMark | None) -> dict | None:
        out = {}
        if shift:
            out["shift"] = {"dir": shift.direction}
            if shift.value:
                out["shift"]["value"] = shift.value
        if requires:
            out["requires"] = (
                {"dir": requires.direction, "rank": requires.rank}
                if requires.check_by_rank
                else {"dir": requires.direction, "value": requires.value}
            )
        return out or None

    # ---------------------------------------------------------------- conditions

    def group(
        self,
        g: ConditionGroup | dict | None,
        dialog: str,
        node: str | None = None,
        negated: bool = False,
    ) -> dict | None:
        if isinstance(g, dict):  # raw nested group (OrAndLogic)
            g = ConditionGroup(
                operation=g.get("Operation") or "And",
                conditions=[
                    Condition(
                        type=c.get("$type", "?"),
                        negated=bool(c.get("Not")),
                        params={
                            k: v for k, v in c.items() if k not in ("$type", "Not")
                        },
                    )
                    for c in g.get("Conditions") or []
                    if isinstance(c, dict)
                ],
            )
        if not g:
            return None
        return _compact(
            {
                "op": g.operation.lower(),
                "not": negated,
                "items": [self.condition(c, dialog, node) for c in g.conditions],
            }
        )

    def condition(self, c: Condition, dialog: str, node: str | None) -> dict:
        checker = c.params.get("ConditionsChecker")
        if c.type == "OrAndLogic" and isinstance(checker, dict):
            nested = self.group(checker, dialog, node, c.negated)
            if nested:
                return nested
        leaf = {
            "type": c.type,
            "not": c.negated,
            "label": self.desc.condition(c, dialog=dialog, node=node),
        }
        leaf.update(self.typed_fields(c))
        return _compact(leaf)

    def typed_fields(self, c: Condition) -> dict[str, Any]:
        p, t = c.params, c.type
        if t in _NODE_REFS:
            target = _bp(p.get(_NODE_REFS[t]))
            if not target:
                return {}
            out: dict[str, Any] = {"node": target}
            entry = self.desc.nodes.get(target)
            if entry:
                out["dialog"] = entry[0].id
                if t in ("CueSeen", "AnswerSelected"):
                    out["text"] = _key(getattr(entry[1], "text", None))
            if p.get("CurrentDialog"):
                out["scope"] = "dialog"
            return out
        if t == "DialogSeen":
            target = _bp(p.get("m_Dialog"))
            return {"dialog": target} if target in self.all_dialogs else {}
        if t == "CompanionInParty":
            return {
                "companion": self.companion(p.get("m_companion")),
                "match": [s for k, s in _COMPANION_STATES.items() if p.get(k)],
                "includeDead": bool(p.get("IncludeDead")),
            }
        if t in ("CompanionIsDead", "CompanionIsLost"):
            unit = p.get("m_companion") or p.get("m_Companion")
            return {"companion": self.companion(unit)}
        if t == "CheckIsPlayerDominantSoulmark":
            return {"dir": p.get("m_Direction")}
        if t == "CurrentChapter":
            return {"chapter": p.get("Chapter")}
        return {}

    def companion(self, raw: Any) -> str | None:
        unit = _bp(raw)
        if not unit:
            return None
        name = self.db.speakers.get(unit, unit)
        self.companions.add(name)
        return name

    # --------------------------------------------------------------------- nodes

    def node(self, n: NodeType, dialog: str) -> dict:
        def cond(g: ConditionGroup) -> dict | None:
            return self.group(g, dialog, n.id)

        out: dict[str, Any]
        if isinstance(n, Cue):
            out = {
                "kind": "cue",
                "text": _key(n.text),
                "speaker": n.speaker.name,
                "narrator": n.narrator or n.speaker.no_speaker,
                "if": cond(n.conditions),
                "once": _once(n),
                "continue": self.cue_list(n.continue_cues),
                "answers": list(n.answers),
                "soulMark": self.soul_mark(n.soul_mark_shift, n.soul_mark_requirement),
                "actions": self.actions(show=n.on_show, stop=n.on_stop),
            }
        elif isinstance(n, AnswersList):
            out = {
                "kind": "answers",
                "answers": list(n.answers),
                "if": cond(n.conditions),
                "once": _once(n),
                "soulMark": self.soul_mark(None, n.soul_mark_requirement),
            }
        elif isinstance(n, Answer):
            sc = n.skill_check
            out = {
                "kind": "answer",
                "text": _key(n.text),
                "next": self.cue_list(n.next_cues),
                "show": cond(n.show_conditions),
                "select": cond(n.select_conditions),
                "once": _once(n),
                "tag": check_tag(sc.type, sc.difficulty, sc.dc) if sc else None,
                "fakeTags": [
                    check_tag(f.type, f.difficulty, f.dc) for f in n.fake_checks
                ],
                "by": n.character_selection,
                "soulMark": self.soul_mark(n.soul_mark_shift, n.soul_mark_requirement),
                "actions": self.actions(
                    select=n.on_select, success=n.on_check_success, fail=n.on_check_fail
                ),
            }
        elif isinstance(n, Check):
            out = {
                "kind": "check",
                "tag": check_tag(n.skill, n.difficulty, n.dc),
                "hidden": n.hidden,
                "success": n.success,
                "fail": n.fail,
                "if": cond(n.conditions),
                "once": _once(n),
                "actions": self.actions(success=n.on_success, fail=n.on_fail),
            }
        elif isinstance(n, CueSequence):
            out = {
                "kind": "sequence",
                "cues": list(n.cues),
                "exit": n.exit,
                "if": cond(n.conditions),
                "once": _once(n),
            }
        elif isinstance(n, SequenceExit):
            out = {
                "kind": "exit",
                "answers": list(n.answers),
                "continue": self.cue_list(n.continue_cues),
            }
        elif isinstance(n, BookPage):
            out = {
                "kind": "page",
                "cues": list(n.cues),
                "answers": list(n.answers),
                "if": cond(n.conditions),
                "once": _once(n),
                "actions": self.actions(show=n.on_show),
            }
        else:
            raise TypeError(f"unknown node type {type(n).__name__}")
        out["comment"] = n.comment
        out["deleted"] = n.deleted
        return _compact(out)

    # --------------------------------------------------------------------- files

    def dialog(self, d: Dialog) -> dict:
        return _compact(
            {
                "id": d.id,
                "name": d.name.strip(),
                "deleted": d.deleted,
                "comment": d.comment,
                "if": self.group(d.conditions, d.id),
                "start": self.cue_list(d.first_cue),
                "actions": self.actions(
                    start=d.start_actions,
                    finish=d.finish_actions,
                    replace=d.replace_actions,
                ),
                "nodes": {n.id: self.node(n, d.id) for n in self.included(d)},
            }
        )

    def index_entry(self, d: Dialog) -> dict:
        name = d.name.strip()
        path = d.directory.removeprefix("Blueprints/")
        tags = dialog_tags(path, name)
        nodes = self.included(d)
        speakers = collections.Counter(
            n.speaker.name for n in nodes if isinstance(n, Cue) and n.speaker.name
        )
        by_frequency = sorted(speakers.items(), key=lambda kv: (-kv[1], kv[0]))
        return _compact(
            {
                "id": d.id,
                "name": name,
                "path": path,
                "tags": tags,
                "chapter": dialog_chapter(tags),
                "source": d.source,
                "type": d.type,
                "deleted": d.deleted,
                "nodes": len(nodes),
                "speakers": [s for s, _ in by_frequency],
            }
        )

    def strings(self, locale: str) -> dict:
        groups: dict[str, dict[str, str]] = {}
        fallback: set[str] = set()
        for d in self.dialogs:
            group: dict[str, str] = {}
            for n in self.included(d):
                ls = getattr(n, "text", None)
                if not ls or ls.missing or ls.key in group:
                    continue
                text = ls.texts.get(locale)
                if not text:
                    text = ls.texts.get(FALLBACK_LOCALE)
                    if not text:
                        continue
                    fallback.add(ls.key)
                group[ls.key] = text
            if group:
                groups[d.id] = group
        return {"locale": locale, "dialogs": groups, "fallback": sorted(fallback)}

    def write(self, out: Path) -> None:
        """Write the bundle atomically (via a temporary file next to ``out``)."""
        tmp = out.with_name(out.name + ".tmp")
        nodes = 0
        with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
            for d in self.dialogs:
                data = self.dialog(d)
                nodes += len(data.get("nodes", {}))
                z.writestr(f"dialogs/{d.id}.json", _dumps(data))
            z.writestr(
                "index.json",
                _dumps({"dialogs": [self.index_entry(d) for d in self.dialogs]}),
            )
            for loc in self.locales:
                z.writestr(f"strings/{loc}.json", _dumps(self.strings(loc)))
            manifest = {
                "format": FORMAT,
                "version": VERSION,
                "generatedAt": datetime.now(timezone.utc).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                ),
                "sourceFingerprint": self.db.source_fingerprint,
                "locales": self.locales,
                "fallbackLocale": FALLBACK_LOCALE,
                "companions": sorted(self.companions),
                "counts": {"dialogs": len(self.dialogs), "nodes": nodes},
            }
            z.writestr("manifest.json", _dumps(manifest))
        tmp.replace(out)


def select_locales(db: DialogDatabase, spec: str | None) -> list[str]:
    if not spec:
        return [loc for loc in db.locales if loc != "dev"]
    wanted = [w.strip() for w in spec.split(",") if w.strip()]
    for w in wanted:
        if w not in db.locales:
            print(
                f"warning: locale {w!r} not in the data (available: {', '.join(db.locales)})",
                file=sys.stderr,
            )
    return [w for w in dict.fromkeys(wanted) if w in db.locales]


# --------------------------------------------------------------------- format


class ExplorerBundle:
    name = "explorer-bundle"
    help = "compact zip bundle for the dialog explorer (spec: EXPLORER_BUNDLE.md)"

    @staticmethod
    def add_arguments(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--locales",
            metavar="LOC[,LOC…]",
            help="locales to include, e.g. enGB,deDE (default: all except dev); texts missing in "
            "a locale fall back to enGB",
        )
        add_dialog_selection(p, default="all")
        p.add_argument(
            "--output-file",
            default="dialogs-explorer-bundle.zip",
            help="file to write (default: dialogs-explorer-bundle.zip)",
        )

    @staticmethod
    def run(db: DialogDatabase, args: argparse.Namespace) -> int:
        locales = select_locales(db, args.locales)
        if not locales:
            print("error: no valid locale selected", file=sys.stderr)
            return 2
        dialogs = select_dialogs(db, args.dialogs)
        out = Path(args.output_file)
        BundleBuilder(db, dialogs, locales).write(out)
        print(
            f"wrote {len(dialogs)} dialogs, locales {', '.join(locales)} to {out} "
            f"({out.stat().st_size / 1e6:.1f} MB)",
            file=sys.stderr,
        )
        return 0
