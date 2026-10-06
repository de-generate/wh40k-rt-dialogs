// Plays a dialog along a list of user choices (EXPLORER_BUNDLE.md §5.3).
//
// The player does not simulate the game. Wherever the game decides, the user chooses; conditions are only labels.
// A choice point with a single option proceeds automatically. Options come in a fixed order, so a path is just
// the list of chosen option indices.
//
// Sequences keep a stack of frames. A branch that ends (a node without a way forward) returns to the innermost
// sequence; with no sequence left, the dialog ends. Sequence entries may have their own flow; the user then picks
// between the next entry of the sequence and that flow.

import type { CueList, Dialog, DialogNode } from "../bundle/types";

type Op =
  | { t: "visit"; id: string; entry?: boolean } // entry: visited as a sequence entry
  | { t: "end" } // end of the current branch
  | { t: "resume" }; // next entry of the innermost sequence

interface Frame {
  seq: string;
  next: number;
}

export type OptionKind =
  | "node" // go to a node: alternative, answer list, answer, sequence entry
  | "end" // the branch ends here (fall-through)
  | "resume" // go on with the enclosing sequence
  | "success"
  | "fail"
  | "play" // play a conditional sequence entry
  | "skip"; // skip it

export interface Option {
  kind: OptionKind;
  /** Target node, for "node", "success", "fail" and "play". Absent when a check branch leads nowhere. */
  id?: string;
  /** Offered only because every other option is conditional. */
  fallthrough?: boolean;
  /** The option belongs to a random cue list. */
  random?: boolean;
  /** "end" resumes an enclosing sequence instead of ending the dialog. */
  resumes?: boolean;
  op: Op;
}

export type ChoiceKind = "alternatives" | "answers" | "check" | "entry";

export interface ChoicePoint {
  kind: ChoiceKind;
  /** The node that offers the choice (absent for the dialog's start list). */
  at?: string;
  options: Option[];
}

export type Step =
  | { kind: "node"; id: string; node: DialogNode }
  | { kind: "missing"; id: string }
  | { kind: "choice"; point: ChoicePoint; index: number }
  | { kind: "end" }
  | { kind: "loop" };

export interface PlayResult {
  steps: Step[];
  /** The choice waiting for the user, or null when the dialog has ended. */
  pending: ChoicePoint | null;
  /** Number of choices consumed; less than given if the path became invalid. */
  used: number;
  /** The path contained an index that doesn't exist at its choice point. */
  invalid: boolean;
}

/** Upper bound for automatic steps between two choices; protects against cycles without choices. */
const MAX_AUTO_OPS = 10_000;

class Machine {
  steps: Step[] = [];

  constructor(
    private nodes: Record<string, DialogNode>,
    public stack: Frame[] = [],
  ) {}

  fork(): Machine {
    return new Machine(
      this.nodes,
      this.stack.map((f) => ({ ...f })),
    );
  }

  /** Executes an operation; returns the next choice point, or null when the dialog ends. */
  exec(op: Op): ChoicePoint | null {
    switch (op.t) {
      case "visit":
        return this.visit(op.id, op.entry ?? false);
      case "end":
        if (this.stack.length > 0) return this.resume();
        this.steps.push({ kind: "end" });
        return null;
      case "resume":
        return this.resume();
    }
  }

  start(list: CueList | undefined): ChoicePoint | null {
    if (!list || list.alts.length === 0) {
      this.steps.push({ kind: "end" });
      return null;
    }
    return this.cueList("alternatives", undefined, list);
  }

  private visit(id: string, entry: boolean): ChoicePoint {
    const node = this.nodes[id];
    if (!node) {
      this.steps.push({ kind: "missing", id });
      return this.single({ t: "end" });
    }
    switch (node.kind) {
      case "cue":
        this.steps.push({ kind: "node", id, node });
        return this.tail(id, node.continue, node.answers, entry);
      case "exit":
        return this.tail(id, node.continue, node.answers, false);
      case "answers":
        return this.answerList(id, node.answers);
      case "answer":
        this.steps.push({ kind: "node", id, node });
        return this.cueList("alternatives", id, node.next);
      case "check":
        this.steps.push({ kind: "node", id, node });
        return {
          kind: "check",
          at: id,
          options: [
            branch("success", node.success, this.stack.length > 0),
            branch("fail", node.fail, this.stack.length > 0),
          ],
        };
      case "sequence":
        this.steps.push({ kind: "node", id, node });
        this.stack.push({ seq: id, next: 0 });
        return this.resume();
      case "page":
        this.steps.push({ kind: "node", id, node });
        return this.answerList(id, node.answers);
    }
  }

  private resume(): ChoicePoint {
    const frame = this.stack[this.stack.length - 1];
    const seq = this.nodes[frame.seq];
    const cues = seq?.kind === "sequence" ? (seq.cues ?? []) : [];
    if (frame.next < cues.length) {
      const id = cues[frame.next++];
      const visit: Op = { t: "visit", id, entry: true };
      if (!this.conditional(id)) return this.single(visit);
      return {
        kind: "entry",
        at: id,
        options: [
          { kind: "play", id, op: visit },
          { kind: "skip", op: { t: "resume" } },
        ],
      };
    }
    this.stack.pop();
    const exit = seq?.kind === "sequence" ? seq.exit : undefined;
    return this.single(exit ? { t: "visit", id: exit } : { t: "end" });
  }

  /** The way forward after a cue or exit: `continue` alternatives, then entries of `answers`. */
  private tail(at: string, cont: CueList | undefined, answers: string[] | undefined, entry: boolean): ChoicePoint {
    const options: Option[] = [
      ...(cont?.alts ?? []).map((id) => this.nodeOption(id, cont?.random)),
      ...(answers ?? []).map((id) => this.nodeOption(id)),
    ];
    if (entry && options.length > 0) {
      // The entry's own flow may or may not apply inside the sequence; offer the sequence first.
      return { kind: "alternatives", at, options: [{ kind: "resume", op: { t: "resume" } }, ...options] };
    }
    return this.withFallthrough("alternatives", at, options);
  }

  private cueList(kind: ChoiceKind, at: string | undefined, list: CueList | undefined): ChoicePoint {
    const options = (list?.alts ?? []).map((id) => this.nodeOption(id, list?.random));
    return this.withFallthrough(kind, at, options);
  }

  private answerList(at: string, answers: string[] | undefined): ChoicePoint {
    const options = (answers ?? []).map((id) => this.nodeOption(id));
    return options.length > 0 ? { kind: "answers", at, options } : this.single({ t: "end" });
  }

  /** Adds the end of the branch when every option is conditional, so the game may find none that passes. */
  private withFallthrough(kind: ChoiceKind, at: string | undefined, options: Option[]): ChoicePoint {
    if (options.every((o) => o.id !== undefined && this.conditional(o.id))) {
      options.push({ kind: "end", fallthrough: options.length > 0, resumes: this.stack.length > 0, op: { t: "end" } });
    }
    return { kind, at, options };
  }

  private nodeOption(id: string, random?: boolean): Option {
    const option: Option = { kind: "node", id, op: { t: "visit", id } };
    if (random) option.random = true;
    return option;
  }

  private single(op: Op): ChoicePoint {
    const kind: OptionKind = op.t === "resume" ? "resume" : op.t === "end" ? "end" : "node";
    return { kind: "alternatives", options: [{ kind, op, resumes: op.t === "end" && this.stack.length > 0 }] };
  }

  /** Whether the game might skip the node: it has conditions or is shown only once. */
  conditional(id: string): boolean {
    const node = this.nodes[id];
    if (!node) return false;
    if (node.once || node.if) return true;
    return node.kind === "answer" && node.show !== undefined;
  }
}

function branch(kind: "success" | "fail", id: string | undefined, resumes: boolean): Option {
  return id ? { kind, id, op: { t: "visit", id } } : { kind, resumes, op: { t: "end" } };
}

function stateKey(op: Op, stack: Frame[]): string {
  return JSON.stringify([op, stack]);
}

/** Runs automatic steps until a real choice (two or more options) or the end. */
function advance(m: Machine, point: ChoicePoint | null): ChoicePoint | null {
  const seen = new Set<string>();
  let ops = 0;
  while (point && point.options.length === 1) {
    const op = point.options[0].op;
    const key = stateKey(op, m.stack);
    if (seen.has(key) || ++ops > MAX_AUTO_OPS) {
      m.steps.push({ kind: "loop" });
      return null;
    }
    seen.add(key);
    point = m.exec(op);
  }
  return point;
}

export function play(dialog: Dialog, path: readonly number[]): PlayResult {
  const m = new Machine(dialog.nodes ?? {});
  let point = advance(m, m.start(dialog.start));
  let used = 0;
  while (point && used < path.length) {
    const index = path[used];
    const option = point.options[index];
    if (!option) return { steps: m.steps, pending: point, used, invalid: true };
    used++;
    if (point.kind !== "answers") m.steps.push({ kind: "choice", point, index });
    point = advance(m, m.exec(option.op));
  }
  return { steps: m.steps, pending: point, used, invalid: false };
}

/** Node ids whose text keys belong to a step, including the cues shown on a page. */
export function stepTextKeys(step: Step, nodes: Record<string, DialogNode>): string[] {
  if (step.kind !== "node") return [];
  const node = step.node;
  if (node.kind === "cue" || node.kind === "answer") return node.text ? [node.text] : [];
  if (node.kind === "page") {
    return (node.cues ?? []).flatMap((id) => {
      const cue = nodes[id];
      return cue?.kind === "cue" && cue.text ? [cue.text] : [];
    });
  }
  return [];
}

/**
 * Finds the shortest path (fewest choices) that plays a step matching `match`, by breadth-first search over
 * player states. Returns null if no such path exists within the limits.
 */
export function findPath(
  dialog: Dialog,
  match: (step: Step) => boolean,
  { maxStates = 50_000, maxDepth = 16 } = {},
): number[] | null {
  const root = new Machine(dialog.nodes ?? {});
  let point = advance(root, root.start(dialog.start));
  if (root.steps.some(match)) return [];
  if (!point) return null;

  type State = { m: Machine; point: ChoicePoint; path: number[] };
  let queue: State[] = [{ m: root, point, path: [] }];
  const seen = new Set<string>();
  let states = 0;
  while (queue.length > 0) {
    const nextQueue: State[] = [];
    for (const { m, point, path } of queue) {
      for (let i = 0; i < point.options.length; i++) {
        const op = point.options[i].op;
        const key = stateKey(op, m.stack);
        if (seen.has(key)) continue;
        seen.add(key);
        if (++states > maxStates) return null;
        const child = m.fork();
        const next = advance(child, child.exec(op));
        if (child.steps.some(match)) return [...path, i];
        if (next && child.stack.length <= maxDepth) nextQueue.push({ m: child, point: next, path: [...path, i] });
      }
    }
    queue = nextQueue;
  }
  return null;
}
