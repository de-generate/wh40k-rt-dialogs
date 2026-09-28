"""Labeled-script text rendering of dialogs.

A dialog is printed as a script: consecutive lines are printed one after another,
player answers are numbered and indented below the line offering them, and every
node that can be reached from more than one place (or would be nested too deep)
is printed once as a labeled section ``[B] ----`` that other places jump to with
``→ [B]``.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ..describe import Describer, check_tag, is_narration
from ..model import (
    Answer,
    AnswersList,
    BookPage,
    Check,
    Cue,
    CueList,
    CueSequence,
    Dialog,
    DialogDatabase,
    SequenceExit,
)
from .common import add_dialog_selection, decode_escapes, select_dialogs

WIDTH = 80
MAX_INDENT = 32  # deeper content is moved into its own labeled section


def label_name(i: int) -> str:
    """0 -> A, 25 -> Z, 26 -> AA, …"""
    s = ""
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


def _node_conditions(node) -> object:
    return getattr(node, "conditions", None) or getattr(node, "show_conditions", None)


class DialogRenderer:
    def __init__(self, dialog: Dialog, desc: Describer):
        self.d = dialog
        self.desc = desc
        self.nodes = dialog.nodes
        self.lines: list[str] = []
        self.labels: dict[str, str] = {}
        self.queue: list[str] = []
        self.rendered: set[str] = set()
        self.indegree = self._indegree()

    # ------------------------------------------------------------ structure

    def _answers_used(self, node: Cue | SequenceExit) -> bool:
        """Continue takes precedence over answers; answers only matter if every continue option is conditional."""
        if not node.answers:
            return False
        if not node.continue_cues:
            return True
        return all(
            _node_conditions(self.nodes.get(c)) or self._once(self.nodes.get(c))
            for c in node.continue_cues.cues
        )

    def flow_children(self, node) -> list[str]:
        """Edges as rendered (sequence/page items are printed inline and are not edges)."""
        if isinstance(node, (Cue, SequenceExit)):
            return node.continue_cues.cues + (
                node.answers if self._answers_used(node) else []
            )
        if isinstance(node, AnswersList):
            return list(node.answers)
        if isinstance(node, Answer):
            return list(node.next_cues.cues)
        if isinstance(node, CueSequence):
            return [node.exit] if node.exit else []
        if isinstance(node, Check):
            return [n for n in (node.success, node.fail) if n]
        if isinstance(node, BookPage):
            return list(node.answers)
        return []

    def _indegree(self) -> dict[str, int]:
        indeg: dict[str, int] = {}
        stack = list(self.d.first_cue.cues)
        for c in stack:
            indeg[c] = indeg.get(c, 0) + 1
        seen: set[str] = set()
        while stack:
            nid = stack.pop()
            if nid in seen or nid not in self.nodes:
                continue
            seen.add(nid)
            node = self.nodes[nid]
            items = node.cues if isinstance(node, (CueSequence, BookPage)) else []
            for c in self.flow_children(node):
                indeg[c] = indeg.get(c, 0) + 1
                stack.append(c)
            for c in items:  # items are inline, but their own flow still counts
                if c in self.nodes and c not in seen:
                    seen.add(c)
                    for cc in self._item_children(self.nodes[c]):
                        indeg[cc] = indeg.get(cc, 0) + 1
                        stack.append(cc)
        return indeg

    def _item_children(self, node) -> list[str]:
        # items of sequences/pages are shown as single lines; only nested sequences/checks branch
        if isinstance(node, (CueSequence, Check)):
            return self.flow_children(node)
        return []

    # --------------------------------------------------------------- output

    def emit(self, indent: int, text: str) -> None:
        pad = " " * indent
        for i, line in enumerate(text.split("\n")):
            self.lines.append((pad if i == 0 else pad + "  ") + line)

    def label(self, nid: str) -> str:
        if nid not in self.labels:
            self.labels[nid] = label_name(len(self.labels))
            self.queue.append(nid)
        return self.labels[nid]

    def jump(self, indent: int, nid: str) -> None:
        self.emit(indent, f"→ [{self.label(nid)}]")

    def needs_label(self, nid: str, indent: int) -> bool:
        return (
            nid in self.labels
            or self.indegree.get(nid, 0) > 1
            or indent > MAX_INDENT
            or nid in self.rendered
        )

    def tags(self, node, *extra: str) -> str:
        t = [e for e in extra if e]
        if getattr(node, "show_once", False):
            t.append("(once)")
        elif getattr(node, "show_once_current_dialog", False):
            t.append("(once per conversation)")
        if getattr(node, "soul_mark_requirement", None):
            t.append(self.desc.soul_mark(node.soul_mark_requirement, requirement=True))
        if getattr(node, "soul_mark_shift", None):
            t.append(self.desc.soul_mark(node.soul_mark_shift))
        if node.deleted:
            t.append("(deleted)")
        return ("   " + " ".join(t)) if t else ""

    def cond_text(self, group, node_id: str | None = None) -> str:
        return self.desc.conditions(group, dialog=self.d.id, node=node_id)

    # ---------------------------------------------------------------- nodes

    def flow(
        self,
        nid: str,
        indent: int,
        section_start: bool = False,
        cond_shown: bool = False,
    ) -> None:
        """Render ``nid`` and everything that follows it linearly."""
        first = True
        while nid:
            if nid not in self.nodes:
                self.emit(indent, f"→ <missing node {nid}>")
                return
            if not (first and section_start) and self.needs_label(nid, indent):
                self.jump(indent, nid)
                return
            nid = self.render_one(nid, indent, cond_shown=cond_shown and first)
            first = False

    def render_one(self, nid: str, indent: int, cond_shown: bool = False) -> str | None:
        """Render one node; return the node that follows inline at the same indent (if any)."""
        self.rendered.add(nid)
        node = self.nodes[nid]
        cond = _node_conditions(node)
        if cond and not cond_shown and not isinstance(node, (Answer, AnswersList)):
            self.emit(indent, f"if: {self.cond_text(cond, nid)}")

        if isinstance(node, Cue):
            self.cue_line(node, indent)
            return self.continuation(node, indent)
        if isinstance(node, SequenceExit):
            return self.continuation(node, indent)
        if isinstance(node, CueSequence):
            self.emit(indent, "(in sequence)" + self.tags(node))
            for item in node.cues:
                self.item(item, indent + 2)
            if not node.exit:
                self.emit(indent, "[END]")
            return node.exit
        if isinstance(node, Check):
            self.check(node, indent)
            return None
        if isinstance(node, BookPage):
            self.emit(indent, "(book page)" + self.tags(node))
            for item in node.cues:
                self.item(item, indent + 2)
            self.actions_line(indent + 2, node.on_show)
            if node.answers:
                self.answers(node.answers, indent)
            else:
                self.emit(indent, "[END]")
            return None
        if isinstance(node, AnswersList):
            self.answers([nid], indent, section=True)
            return None
        if isinstance(node, Answer):  # only as the start of a labeled section
            self.emit(indent, f"after choosing {self.desc.snippet(nid)}:")
            return self.next_cues(node.next_cues, indent)
        return None

    def cue_line(self, cue: Cue, indent: int) -> None:
        text = self.desc.text(cue.text)
        raw, _ = self.desc.raw_text(cue.text)
        name = cue.speaker.name
        if cue.speaker.no_speaker or (not name and raw and is_narration(raw)):
            line = text
        else:
            line = f"{name or 'NPC'}: {text}"
        self.emit(indent, line + self.tags(cue))
        self.actions_line(indent + 2, cue.on_show + cue.on_stop)

    def actions_line(self, indent: int, actions) -> None:
        if actions:
            self.emit(indent, f"(actions: {self.desc.actions(actions)})")

    def item(self, nid: str, indent: int) -> None:
        """A cue inside a sequence or book page: printed as a line; nested structures are rendered fully."""
        node = self.nodes.get(nid)
        if node is None:
            self.emit(indent, f"<missing node {nid}>")
            return
        self.rendered.add(nid)
        if isinstance(node, Cue):
            if node.conditions:
                self.emit(indent, f"if: {self.cond_text(node.conditions, nid)}")
            self.cue_line(node, indent)
        else:
            self.flow(nid, indent, section_start=True)

    def continuation(self, node: Cue | SequenceExit, indent: int) -> str | None:
        use_answers = self._answers_used(node)
        if node.continue_cues:
            if not use_answers:
                return self.next_cues(node.continue_cues, indent)
            self.alternatives(node.continue_cues, indent)
            self.emit(indent, "otherwise:")
            self.answers(node.answers, indent + 2)
            return None
        if use_answers:
            self.answers(node.answers, indent)
        else:
            self.emit(indent, "[END]")
        return None

    def next_cues(self, cl: CueList, indent: int) -> str | None:
        """Return the single unconditional next node (rendered inline by the caller), or render alternatives."""
        if not cl.cues:
            self.emit(indent, "[END]")
            return None
        if len(cl.cues) == 1 and not _node_conditions(self.nodes.get(cl.cues[0])):
            return cl.cues[0]
        self.alternatives(cl, indent)
        return None

    def alternatives(self, cl: CueList, indent: int) -> None:
        if len(cl.cues) > 1:
            self.emit(
                indent,
                "One at random:" if cl.strategy == "Random" else "First that applies:",
            )
        all_conditional = True
        for i, nid in enumerate(cl.cues):
            cond = self.alt_condition(nid)
            head = f"{chr(97 + i)}) " if len(cl.cues) > 1 else ""
            if cond:
                self.emit(indent, f"{head}if: {cond}")
            else:
                all_conditional = False
                self.emit(indent, f"{head}always:" if head else "then:")
            self.flow(nid, indent + 3 if head else indent + 2, cond_shown=True)
        if all_conditional and cl.strategy != "Random":
            self.emit(
                indent,
                f"{chr(97 + len(cl.cues))}) otherwise: [END]"
                if len(cl.cues) > 1
                else "otherwise: [END]",
            )

    def _once(self, node) -> str:
        if getattr(node, "show_once", False):
            return "not shown before"
        if getattr(node, "show_once_current_dialog", False):
            return "not shown before in this conversation"
        if (
            isinstance(node, CueSequence)
            and node.cues
            and all(self._once(self.nodes.get(c)) for c in node.cues)
        ):
            return "not shown before"
        return ""

    def alt_condition(self, nid: str) -> str:
        """Why an alternative in a cue list may be skipped: its conditions and/or being show-once."""
        node = self.nodes.get(nid)
        parts = []
        cond = _node_conditions(node)
        if cond:
            parts.append(self.cond_text(cond, nid))
        once = self._once(node)
        if once:
            parts.append(once)
        return " and ".join(parts)

    def check(self, node: Check, indent: int) -> None:
        hidden = " (hidden)" if node.hidden else ""
        self.emit(
            indent,
            f"CHECK [{check_tag(node.skill, node.difficulty, node.dc)}]{hidden}"
            + self.tags(node),
        )
        for label, target, actions in (
            ("success", node.success, node.on_success),
            ("failure", node.fail, node.on_fail),
        ):
            self.emit(indent, f"{label}:")
            self.actions_line(indent + 2, actions)
            if target:
                self.flow(target, indent + 2)
            else:
                self.emit(indent + 2, "[END]")

    # -------------------------------------------------------------- answers

    def answers(self, ids: list[str], indent: int, section: bool = False) -> None:
        nodes = [self.nodes.get(i) for i in ids]
        lists = [(i, n) for i, n in zip(ids, nodes) if isinstance(n, AnswersList)]
        direct = [i for i, n in zip(ids, nodes) if not isinstance(n, AnswersList)]
        if direct:
            self.answer_items(direct, indent)
        if len(lists) == 1 and not direct:
            lid, lst = lists[0]
            if not section and self.needs_label(lid, indent):
                self.jump(indent, lid)
                return
            self.rendered.add(lid)
            if lst.conditions:
                self.emit(
                    indent,
                    f"answers if: {self.cond_text(lst.conditions, lid)}"
                    + self.tags(lst),
                )
            elif self.tags(lst):
                self.emit(indent, "answers:" + self.tags(lst))
            self.answer_items(lst.answers, indent)
            return
        if lists:
            self.emit(indent, "First answer list that applies:")
            for k, (lid, lst) in enumerate(lists):
                cond = (
                    self.cond_text(lst.conditions, lid) if lst.conditions else "always"
                )
                self.emit(indent, f"{chr(97 + k)}) if: {cond}" + self.tags(lst))
                if self.needs_label(lid, indent + 3):
                    self.jump(indent + 3, lid)
                else:
                    self.rendered.add(lid)
                    self.answer_items(lst.answers, indent + 3)

    def answer_items(self, ids: list[str], indent: int) -> None:
        for num, aid in enumerate(ids, 1):
            ans = self.nodes.get(aid)
            prefix = f"{num}. "
            body = indent + len(prefix)
            if not isinstance(ans, Answer):
                self.emit(indent, f"{prefix}<missing answer {aid}>")
                continue
            skill = self.desc.answer_tag(ans)
            nxt = ans.next_cues.cues
            if (
                not skill
                and len(nxt) == 1
                and isinstance(self.nodes.get(nxt[0]), Check)
            ):
                chk = self.nodes[nxt[0]]
                skill = f"[{check_tag(chk.skill, chk.difficulty, chk.dc)}]"
            who = {
                "Companion": "(companion answers) ",
                "Random": "(random character) ",
            }.get(ans.character_selection or "", "")
            text = self.desc.text(ans.text)
            self.emit(
                indent,
                prefix + who + (skill + " " if skill else "") + text + self.tags(ans),
            )
            if ans.show_conditions:
                self.emit(body, f"if: {self.cond_text(ans.show_conditions, aid)}")
            if ans.select_conditions:
                self.emit(
                    body, f"selectable if: {self.cond_text(ans.select_conditions, aid)}"
                )
            self.actions_line(body, ans.on_select)
            if (
                self.indegree.get(aid, 0) > 1
            ):  # shared between answer lists: body in its own section
                self.jump(body, aid)
                continue
            self.rendered.add(aid)
            self.flow_from_list(ans.next_cues, body)

    def flow_from_list(self, cl: CueList, indent: int) -> None:
        nxt = self.next_cues(cl, indent)
        if nxt:
            self.flow(nxt, indent)

    # --------------------------------------------------------------- dialog

    def render(self) -> str:
        d = self.d
        directory = d.directory
        for prefix in ("Blueprints/World/Dialogs/", "Blueprints/DLC/", "Blueprints/"):
            if directory.startswith(prefix):
                directory = directory[len(prefix) :]
                break
        right = f"{d.source} · {d.type}"
        name = d.name.strip()
        self.lines += [
            "=" * WIDTH,
            name + right.rjust(WIDTH - len(name))
            if len(name) + len(right) < WIDTH
            else f"{name}  {right}",
            directory,
        ]
        if d.deleted:
            self.lines.append("DELETED (editor-deleted dialog, not in the game)")
        if d.comment:
            self.lines.append(f"note: {d.comment}")
        if d.conditions:
            self.lines.append(f"if: {self.cond_text(d.conditions)}")
        if d.start_actions:
            self.lines.append(f"on start: {self.desc.actions(d.start_actions)}")
        if d.finish_actions:
            self.lines.append(f"on finish: {self.desc.actions(d.finish_actions)}")
        self.lines += ["=" * WIDTH, ""]

        cues = d.first_cue.cues
        if not cues:
            self.lines.append("(empty dialog)")
        elif (
            len(cues) == 1
            and not _node_conditions(self.nodes.get(cues[0]))
            and self.indegree.get(cues[0], 0) > 1
        ):
            self.label(
                cues[0]
            )  # the start is a loop target: begin directly with its section
        else:
            nxt = self.next_cues(d.first_cue, 2)
            if nxt:
                self.flow(nxt, 2)

        done = 0
        while done < len(self.queue):
            nid = self.queue[done]
            done += 1
            if self.lines and self.lines[-1] != "":
                self.lines.append("")
            head = f"[{self.labels[nid]}] "
            self.lines.append(head + "-" * (WIDTH - len(head)))
            self.flow(nid, 2, section_start=True)

        hidden = sum(1 for n in self.nodes.values() if not n.reachable)
        if hidden:
            self.lines += [
                "",
                f"({hidden} unreachable node{'s' if hidden > 1 else ''} not shown)",
            ]
        return "\n".join(self.lines)


def render_dialog(dialog: Dialog, desc: Describer) -> str:
    return DialogRenderer(dialog, desc).render()


# --------------------------------------------------------------------- format


class LabeledScriptSingle:
    name = "labeled-script-single"
    help = "all selected dialogs as a labeled script in one text file"

    @staticmethod
    def add_arguments(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "--lang",
            default="enGB",
            help="locale of the text, e.g. enGB, deDE, ruRU, zhCN; lines missing in that locale fall "
            "back to enGB and are marked [enGB] (default: enGB)",
        )
        p.add_argument(
            "--separator",
            default=r"\n\n\n",
            help=r"text placed between two dialogs; \n, \t and \\ escapes are understood "
            r'(default: "\n\n\n")',
        )
        add_dialog_selection(p)
        p.add_argument(
            "--output-file",
            default="dialogs-labeled-script-single.txt",
            help="file to write (default: dialogs-labeled-script-single.txt)",
        )

    @staticmethod
    def run(db: DialogDatabase, args: argparse.Namespace) -> int:
        if args.lang not in db.locales:
            print(
                f"warning: locale {args.lang!r} not in the data (available: {', '.join(db.locales)})",
                file=sys.stderr,
            )
        dialogs = select_dialogs(db, args.dialogs)
        desc = Describer(db, args.lang)
        separator = decode_escapes(args.separator)
        out = Path(args.output_file)
        with open(out, "w", encoding="utf-8", newline="\n") as fh:
            for i, dialog in enumerate(dialogs):
                if i:
                    fh.write(separator)
                fh.write(render_dialog(dialog, desc))
            fh.write("\n")
        print(
            f"wrote {len(dialogs)} dialogs to {out} ({out.stat().st_size / 1e6:.1f} MB)",
            file=sys.stderr,
        )
        return 0
