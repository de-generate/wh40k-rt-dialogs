"""Human-readable descriptions of texts, conditions, actions etc. (shared by output formats)."""

from __future__ import annotations

import re
from typing import Any

from .model import (
    Action,
    Answer,
    Check,
    Condition,
    ConditionGroup,
    DialogDatabase,
    LocalizedString,
    SkillCheck,
    SoulMark,
)

FALLBACK_LOCALE = "enGB"

_MARKUP = [
    (re.compile(r"</?(?:b|i|u|size|color)(?:=[^>]*)?>"), ""),  # Unity rich text
    (re.compile(r"<br\s*/?>"), "\n"),
    (re.compile(r"\{n\}(.*?)\{/n\}", re.S), r"*\1*"),  # narration
    (re.compile(r"\{[gd]\|[^}]*\}(.*?)\{/[gd]\}", re.S), r"\1"),  # glossary links
    (re.compile(r"\{mf\|([^|}]*)\|([^}]*)\}"), r"\1/\2"),  # male/female variants
    (re.compile(r"\{name\}", re.I), "<Name>"),
    (re.compile(r"\{petname\}", re.I), "<PetName>"),
    (re.compile(r"\{br\}"), "\n"),
    (re.compile(r"\{/?n\}"), "*"),  # unbalanced leftovers
]


def clean_markup(text: str) -> str:
    for pattern, repl in _MARKUP:
        text = pattern.sub(repl, text)
    return text.strip()


def is_narration(raw: str) -> bool:
    """The whole text is a single ``{n}…{/n}`` block (description, nobody speaks)."""
    raw = raw.strip()
    return raw.startswith("{n}") and raw.endswith("{/n}") and raw.count("{n}") == 1


_SKILL_NAMES = {
    "LoreXenos": "Lore (Xenos)",
    "LoreImperium": "Lore (Imperium)",
    "LoreWarp": "Lore (Warp)",
    "TechUse": "Tech-Use",
    "WeaponSkill": "Weapon Skill",
    "BallisticSkill": "Ballistic Skill",
}


def skill_name(t: str | None) -> str:
    if not t:
        return "?"
    for prefix in ("Skill", "Warhammer", "Check"):
        if t.startswith(prefix) and len(t) > len(prefix):
            t = t[len(prefix) :]
            break
    return _SKILL_NAMES.get(t, t)


def check_tag(skill: str | None, difficulty: str | None, dc: int = 0) -> str:
    parts = [skill_name(skill)]
    if difficulty and difficulty != "Custom":
        parts.append(difficulty)
    elif dc:
        parts.append(f"DC {dc}")
    return ", ".join(parts)


def short_id(i: str) -> str:
    return i[:8]


class Describer:
    """Turns model objects into short strings, resolving references through the database."""

    def __init__(
        self, db: DialogDatabase, lang: str = FALLBACK_LOCALE, snippet_len: int = 40
    ):
        self.db = db
        self.lang = lang
        self.snippet_len = snippet_len
        self.nodes = db.node_index()
        self.dialogs = db.dialog_by_id()

    # ---------------------------------------------------------------- texts

    def raw_text(self, ls: LocalizedString | None) -> tuple[str | None, bool]:
        """(text in the selected language or the fallback, used_fallback)."""
        if ls is None or ls.missing:
            return None, False
        t = ls.texts.get(self.lang)
        if t:
            return t, False
        t = ls.texts.get(FALLBACK_LOCALE)
        return (t, True) if t else (None, False)

    def text(self, ls: LocalizedString | None) -> str:
        if ls is None:
            return "(no text)"
        if ls.missing:
            return f"<missing text {ls.key}>"
        raw, fallback = self.raw_text(ls)
        if raw is None:
            return f"<no {self.lang} text>"
        return (f"[{FALLBACK_LOCALE}] " if fallback else "") + clean_markup(raw)

    def snippet(self, node_id: str) -> str:
        entry = self.nodes.get(node_id)
        if entry is None:
            return f"<{short_id(node_id)}>"
        node = entry[1]
        ls = getattr(node, "text", None)
        raw, _ = self.raw_text(ls)
        if not raw:
            return f"<{node.KIND} {short_id(node_id)}>"
        t = " ".join(clean_markup(raw).split())
        if len(t) > self.snippet_len:
            t = t[: self.snippet_len].rstrip() + "…"
        return t if t.startswith(('"', "*", "[", "«", "“")) else f'"{t}"'

    # ----------------------------------------------------------- references

    def ref(self, value: Any) -> str:
        """Readable name for a ``!bp_`` reference (or any other raw value)."""
        if isinstance(value, str) and value.startswith("!bp_"):
            i = value[4:]
            if i in self.db.speakers:
                return self.db.speakers[i]
            if i in self.dialogs:
                return f"dialog {self.dialogs[i].name.strip()}"
            if i in self.nodes:
                return self.snippet(i)
            return short_id(i)
        if isinstance(value, dict) and "$type" in value:
            return value["$type"]
        return str(value)

    def _in_other_dialog(self, node_id: str, current_dialog: str | None) -> str:
        entry = self.nodes.get(node_id)
        if entry and current_dialog and entry[0].id != current_dialog:
            return f" (in {entry[0].name.strip()})"
        return ""

    # ------------------------------------------------------------ conditions

    def conditions(self, group: ConditionGroup | dict | None, **ctx) -> str:
        if isinstance(group, dict):  # raw nested group inside params (OrAndLogic etc.)
            group = ConditionGroup(
                operation=group.get("Operation") or "And",
                conditions=[
                    Condition(
                        type=c.get("$type", "?"),
                        negated=bool(c.get("Not")),
                        params={
                            k: v for k, v in c.items() if k not in ("$type", "Not")
                        },
                    )
                    for c in group.get("Conditions") or []
                ],
            )
        if not group:
            return ""
        joiner = " or " if group.operation == "Or" else " and "
        return joiner.join(self.condition(c, **ctx) for c in group.conditions)

    def condition(
        self, c: Condition, dialog: str | None = None, node: str | None = None
    ) -> str:
        p, neg = c.params, c.negated
        no = "not " if neg else ""
        t = c.type
        if t == "CueSeen" and "m_Cue" in p:
            cue = p["m_Cue"][4:]
            where = " in this conversation" if p.get("CurrentDialog") else ""
            return f"{no}seen {self.snippet(cue)}{self._in_other_dialog(cue, dialog)}{where}"
        if t == "AnswerSelected" and "m_Answer" in p:
            ans = p["m_Answer"][4:]
            where = " in this conversation" if p.get("CurrentDialog") else ""
            if ans == node:
                return f"{'not ' if neg else ''}chosen before{where}"
            verb = "did not choose" if neg else "chose"
            return (
                f"{verb} {self.snippet(ans)}{self._in_other_dialog(ans, dialog)}{where}"
            )
        if t == "DialogSeen" and "m_Dialog" in p:
            return f"{no}seen {self.ref(p['m_Dialog'])}"
        if t in ("CheckPassed", "CheckFailed") and "m_Check" in p:
            entry = self.nodes.get(p["m_Check"][4:])
            what = (
                check_tag(entry[1].skill, entry[1].difficulty, entry[1].dc)
                if entry and isinstance(entry[1], Check)
                else short_id(p["m_Check"][4:])
            )
            return f"{no}{'passed' if t == 'CheckPassed' else 'failed'} check [{what}]"
        if t == "CompanionInParty" and "m_companion" in p:
            return f"{self.ref(p['m_companion'])} {'not ' if neg else ''}in party"
        if t in ("PcMale", "PcFemale"):
            return f"player is {'not ' if neg else ''}{'male' if t == 'PcMale' else 'female'}"
        if t == "EtudeStatus":
            states = [
                k
                for k in (
                    "NotStarted",
                    "Started",
                    "Playing",
                    "CompletionInProgress",
                    "Completed",
                )
                if p.get(k)
            ]
            return f"{no}etude {self.ref(p.get('m_Etude'))} {'/'.join(states) or '?'}"
        if t == "QuestStatus":
            return f"{no}quest {self.ref(p.get('m_Quest'))} {p.get('State', '?')}"
        if t == "ObjectiveStatus":
            return f"{no}objective {self.ref(p.get('m_QuestObjective'))} {p.get('State', '?')}"
        if t == "FlagUnlocked":
            return f"{no}flag {self.ref(p.get('m_ConditionFlag'))} unlocked"
        if t == "FlagInRange":
            return f"{no}flag {self.ref(p.get('m_Flag'))} in {p.get('MinValue')}..{p.get('MaxValue')}"
        if t == "CheckIsPlayerDominantSoulmark":
            return f"{no}dominant soul mark is {p.get('m_Direction')}"
        if t == "False":
            return "always" if neg else "never"
        if t == "OrAndLogic" and "ConditionsChecker" in p:
            return f"{no}({self.conditions(p['ConditionsChecker'], dialog=dialog, node=node)})"
        return no + self.generic(t, p)

    def generic(self, t: str, params: dict) -> str:
        args = []
        for k, v in params.items():
            if (
                v is False
                or k == "Comment"
                or isinstance(v, (list, dict))
                and "$type" not in v
            ):
                continue
            args.append(
                self.ref(v)
                if isinstance(v, str) and v.startswith("!bp_")
                else f"{k}={self.ref(v)}"
            )
        return f"{t}({', '.join(args)})"

    # --------------------------------------------------------------- others

    @staticmethod
    def actions(actions: list[Action]) -> str:
        out: list[str] = []
        for a in actions:
            if out and out[-1].split("×")[0] == a.type:
                n = int(out[-1].split("×")[1]) + 1 if "×" in out[-1] else 2
                out[-1] = f"{a.type}×{n}"
            else:
                out.append(a.type)
        return ", ".join(out)

    @staticmethod
    def soul_mark(sm: SoulMark | None, requirement: bool = False) -> str:
        if sm is None:
            return ""
        if requirement:
            return f"<requires {sm.direction} {'rank ' + str(sm.rank) if sm.check_by_rank else sm.value}>"
        return f"<{sm.direction} +{sm.value}>" if sm.value else f"<{sm.direction}>"

    @staticmethod
    def skill_check(sc: SkillCheck | None) -> str:
        return f"[{check_tag(sc.type, sc.difficulty, sc.dc)}]" if sc else ""

    def answer_tag(self, answer: Answer) -> str:
        return self.skill_check(answer.skill_check)
