"""Data model for the parsed dialog database.

All classes are plain dataclasses. They are (de)serialized to/from JSON by
:mod:`rt_dialogs.serialize`; field names are used verbatim as JSON keys and
fields whose value equals the default are omitted from the JSON.

Blueprint references in typed fields (``answers``, ``cues``, ``success`` …) are
bare AssetIds (the ``!bp_`` prefix is stripped). Inside the untyped ``params`` /
``extra`` dictionaries the original ``"!bp_<id>"`` form is kept so references
remain distinguishable from other strings. See DIALOG_STRUCTURE.md for the
meaning of the underlying game data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, ClassVar

# --------------------------------------------------------------------------- text


@dataclass(slots=True)
class LocalizedString:
    """One localized string, resolved from ``data/Strings``.

    ``texts`` maps locale (``enGB``, ``ruRU``, ``deDE``, …, ``dev``) to text.
    The ``Sound`` pseudo-locale is not a language and is stored in ``voice_over``.
    """

    key: str
    texts: dict[str, str] = field(default_factory=dict)
    voice_over: str | None = None
    speaker: str | None = None
    speaker_gender: str | None = None
    comment: str | None = None
    source_locale: str | None = None
    traits: list[str] = field(default_factory=list)
    path: str | None = None  # string file, relative to the data root
    shared: bool = False  # referenced through a shared string asset
    missing: bool = False  # key could not be resolved; texts is empty

    def text(self, locale: str = "enGB") -> str | None:
        return self.texts.get(locale)


# ---------------------------------------------------------------- game logic


@dataclass(slots=True)
class Condition:
    type: str  # e.g. "CueSeen", "EtudeStatus"
    negated: bool = False
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ConditionGroup:
    operation: str = "And"  # "And" | "Or"
    conditions: list[Condition] = field(default_factory=list)

    def __bool__(self) -> bool:
        return bool(self.conditions)


@dataclass(slots=True)
class Action:
    type: str  # e.g. "StartEtude", "GiveObjective"
    params: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CueList:
    """Alternatives: the first (``First``) / a random (``Random``) valid entry is played."""

    cues: list[str] = field(default_factory=list)
    strategy: str = "First"

    def __bool__(self) -> bool:
        return bool(self.cues)


@dataclass(slots=True)
class SoulMark:
    direction: str  # "Faith" | "Hope" | "Corruption"
    value: int = 0
    check_by_rank: bool = False
    rank: int = 0
    description: LocalizedString | None = None


@dataclass(slots=True)
class SkillCheck:
    """Skill-check tag shown on an answer (display only)."""

    type: str
    difficulty: str | None = None
    dc: int = 0


@dataclass(slots=True)
class Speaker:
    blueprint: str | None = None  # unit blueprint id (not part of the export)
    name: str | None = None  # internal name, e.g. "AbelardCompanion"
    name_source: str | None = None  # "string" | "blueprint" (via the speaker map)
    no_speaker: bool = False
    portrait: str | None = None


# ---------------------------------------------------------------------- nodes


@dataclass(slots=True, kw_only=True)
class Node:
    """Common fields of every node inside a dialog."""

    KIND: ClassVar[str] = ""
    id: str
    path: str  # blueprint file, relative to the data root
    parent: str | None = None  # editor ParentAsset (hint only)
    comment: str | None = None  # designer note
    deleted: bool = False  # Meta.ShadowDeleted
    reachable: bool = True  # reachable from the dialog's first cue
    extra: dict[str, Any] = field(default_factory=dict)  # remaining raw fields


@dataclass(slots=True, kw_only=True)
class Cue(Node):
    KIND: ClassVar[str] = "Cue"
    text: LocalizedString | None = None
    speaker: Speaker = field(default_factory=Speaker)
    listener: str | None = None
    narrator: bool = False
    animation: str | None = None
    conditions: ConditionGroup = field(default_factory=ConditionGroup)
    show_once: bool = False
    show_once_current_dialog: bool = False
    on_show: list[Action] = field(default_factory=list)
    on_stop: list[Action] = field(default_factory=list)
    answers: list[str] = field(default_factory=list)  # AnswersList (rarely Answer) ids
    continue_cues: CueList = field(default_factory=CueList)
    soul_mark_shift: SoulMark | None = None
    soul_mark_requirement: SoulMark | None = None
    description: LocalizedString | None = None


@dataclass(slots=True, kw_only=True)
class Answer(Node):
    KIND: ClassVar[str] = "Answer"
    text: LocalizedString | None = None
    next_cues: CueList = field(default_factory=CueList)
    show_conditions: ConditionGroup = field(default_factory=ConditionGroup)
    select_conditions: ConditionGroup = field(default_factory=ConditionGroup)
    show_once: bool = False
    show_once_current_dialog: bool = False
    skill_check: SkillCheck | None = None
    fake_checks: list[SkillCheck] = field(default_factory=list)
    character_selection: str | None = (
        None  # "Player" | "Companion" | "Random" (None = default)
    )
    on_select: list[Action] = field(default_factory=list)
    on_check_success: list[Action] = field(default_factory=list)
    on_check_fail: list[Action] = field(default_factory=list)
    soul_mark_shift: SoulMark | None = None
    soul_mark_requirement: SoulMark | None = None
    description: LocalizedString | None = None


@dataclass(slots=True, kw_only=True)
class AnswersList(Node):
    KIND: ClassVar[str] = "AnswersList"
    answers: list[str] = field(default_factory=list)
    conditions: ConditionGroup = field(default_factory=ConditionGroup)
    show_once: bool = False
    soul_mark_requirement: SoulMark | None = None


@dataclass(slots=True, kw_only=True)
class CueSequence(Node):
    KIND: ClassVar[str] = "CueSequence"
    cues: list[str] = field(default_factory=list)  # played in order
    exit: str | None = None  # SequenceExit id
    conditions: ConditionGroup = field(default_factory=ConditionGroup)
    show_once: bool = False
    show_once_current_dialog: bool = False


@dataclass(slots=True, kw_only=True)
class SequenceExit(Node):
    KIND: ClassVar[str] = "SequenceExit"
    answers: list[str] = field(default_factory=list)
    continue_cues: CueList = field(default_factory=CueList)


@dataclass(slots=True, kw_only=True)
class Check(Node):
    KIND: ClassVar[str] = "Check"
    skill: str | None = None
    difficulty: str | None = None
    dc: int = 0
    hidden: bool = False
    success: str | None = None
    fail: str | None = None
    conditions: ConditionGroup = field(default_factory=ConditionGroup)
    on_success: list[Action] = field(default_factory=list)
    on_fail: list[Action] = field(default_factory=list)
    show_once: bool = False
    show_once_current_dialog: bool = False


@dataclass(slots=True, kw_only=True)
class BookPage(Node):
    KIND: ClassVar[str] = "BookPage"
    cues: list[str] = field(default_factory=list)  # text shown on the page
    answers: list[str] = field(
        default_factory=list
    )  # Answer ids (directly, no AnswersList)
    conditions: ConditionGroup = field(default_factory=ConditionGroup)
    on_show: list[Action] = field(default_factory=list)
    show_once: bool = False
    show_once_current_dialog: bool = False


NodeType = Cue | Answer | AnswersList | CueSequence | SequenceExit | Check | BookPage
NODE_CLASSES: dict[str, type[Node]] = {
    c.KIND: c
    for c in (Cue, Answer, AnswersList, CueSequence, SequenceExit, Check, BookPage)
}


def node_children(node: Node) -> list[str]:
    """Ids of the nodes this node leads to (the dialog-flow edges, see DIALOG_STRUCTURE.md §3.1)."""
    if isinstance(node, Cue):
        return node.answers + node.continue_cues.cues
    if isinstance(node, AnswersList):
        return list(node.answers)
    if isinstance(node, Answer):
        return list(node.next_cues.cues)
    if isinstance(node, CueSequence):
        return node.cues + ([node.exit] if node.exit else [])
    if isinstance(node, SequenceExit):
        return node.answers + node.continue_cues.cues
    if isinstance(node, Check):
        return [n for n in (node.success, node.fail) if n]
    if isinstance(node, BookPage):
        return node.cues + node.answers
    return []


# ----------------------------------------------------------------- top level


@dataclass(slots=True, kw_only=True)
class Dialog:
    id: str
    name: str  # entry-point file name without extension
    path: str  # entry-point file, relative to the data root
    source: str  # "World" | "DLC1" | "DLC2" | "DLC3"
    type: str = "Common"  # "Common" | "Book" | "StarSystemEvent" | "Epilog"
    comment: str | None = None
    deleted: bool = False
    first_cue: CueList = field(default_factory=CueList)
    conditions: ConditionGroup = field(default_factory=ConditionGroup)
    start_actions: list[Action] = field(default_factory=list)
    finish_actions: list[Action] = field(default_factory=list)
    replace_actions: list[Action] = field(default_factory=list)
    description: LocalizedString | None = None
    nodes: dict[str, NodeType] = field(default_factory=dict)  # AssetId -> node
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def directory(self) -> str:
        return self.path.rsplit("/", 1)[0]


@dataclass(slots=True, kw_only=True)
class BanterResponse:
    unit: str | None = None
    speaker: str | None = None
    weight: float = 0.0
    text: LocalizedString | None = None
    conditions: ConditionGroup = field(default_factory=ConditionGroup)


@dataclass(slots=True, kw_only=True)
class Banter:
    id: str
    name: str
    path: str
    source: str
    comment: str | None = None
    deleted: bool = False
    unit: str | None = None  # who says the first phrase
    speaker: str | None = None  # resolved internal name of ``unit``
    weight: float = 0.0
    response_required: bool = False
    unique: bool = False
    min_chapter: int = 0
    max_chapter: int = 0
    conditions: ConditionGroup = field(default_factory=ConditionGroup)
    first_phrases: list[LocalizedString] = field(default_factory=list)  # alternatives
    response_strategy: str | None = None
    responses: list[BanterResponse] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True, kw_only=True)
class BanterList:
    id: str
    name: str
    path: str
    source: str
    deleted: bool = False
    weight: float = 0.0
    banters: list[str] = field(default_factory=list)


SCHEMA_VERSION = 1


@dataclass(slots=True, kw_only=True)
class DialogDatabase:
    schema_version: int = SCHEMA_VERSION
    generated_at: str = ""
    data_root: str = ""
    source_fingerprint: str = (
        ""  # hash of input file paths/sizes/mtimes (staleness check)
    )
    locales: list[str] = field(default_factory=list)
    speakers: dict[str, str] = field(
        default_factory=dict
    )  # unit blueprint id -> internal name
    dialogs: list[Dialog] = field(default_factory=list)
    banters: list[Banter] = field(default_factory=list)
    banter_lists: list[BanterList] = field(default_factory=list)
    issues: list[str] = field(default_factory=list)  # problems found while parsing

    def dialog_by_id(self) -> dict[str, Dialog]:
        return {d.id: d for d in self.dialogs}

    def node_index(self) -> dict[str, tuple[Dialog, NodeType]]:
        """AssetId -> (dialog, node) for every node of every dialog."""
        return {nid: (d, n) for d in self.dialogs for nid, n in d.nodes.items()}
