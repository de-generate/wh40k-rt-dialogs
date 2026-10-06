import { describe, expect, it } from "vitest";
import type { Dialog, DialogNode } from "../bundle/types";
import { findPath, play, stepTextKeys, type Step } from "./engine";

function dialog(start: string[], nodes: Record<string, DialogNode>): Dialog {
  return { id: "d", name: "Test", start: { alts: start }, nodes };
}

const cond = { op: "and" as const, items: [{ type: "EtudeStatus", label: "etude" }] };

/** Compact trace: node ids, "?" for missing, "#i" for choices, "END" and "LOOP". */
function trace(steps: Step[]): string[] {
  return steps.map((s) => {
    switch (s.kind) {
      case "node":
        return s.id;
      case "missing":
        return `?${s.id}`;
      case "choice":
        return `#${s.index}`;
      case "end":
        return "END";
      case "loop":
        return "LOOP";
    }
  });
}

describe("play", () => {
  it("follows single unconditional ways automatically", () => {
    const d = dialog(["c1"], {
      c1: { kind: "cue", text: "t1", continue: { alts: ["c2"] } },
      c2: { kind: "cue", text: "t2" },
    });
    const r = play(d, []);
    expect(trace(r.steps)).toEqual(["c1", "c2", "END"]);
    expect(r.pending).toBeNull();
  });

  it("offers answers and follows the chosen one", () => {
    const d = dialog(["c1"], {
      c1: { kind: "cue", text: "t1", answers: ["al"] },
      al: { kind: "answers", answers: ["a1", "a2"] },
      a1: { kind: "answer", text: "x", next: { alts: ["c2"] } },
      a2: { kind: "answer", text: "y" },
      c2: { kind: "cue", text: "t2" },
    });
    expect(play(d, []).pending?.options.map((o) => o.id)).toEqual(["a1", "a2"]);
    expect(trace(play(d, [0]).steps)).toEqual(["c1", "a1", "c2", "END"]);
    expect(trace(play(d, [1]).steps)).toEqual(["c1", "a2", "END"]);
  });

  it("offers fall-through only when every alternative is conditional", () => {
    const conditional = dialog(["c1", "c2"], {
      c1: { kind: "cue", text: "t1", if: cond },
      c2: { kind: "cue", text: "t2", once: "always" },
    });
    const kinds = play(conditional, []).pending?.options.map((o) => o.kind);
    expect(kinds).toEqual(["node", "node", "end"]);
    expect(trace(play(conditional, [2]).steps)).toEqual(["#2", "END"]);

    const open = dialog(["c1", "c2"], {
      c1: { kind: "cue", text: "t1", if: cond },
      c2: { kind: "cue", text: "t2" },
    });
    expect(play(open, []).pending?.options.map((o) => o.kind)).toEqual(["node", "node"]);
  });

  it("offers continue and answers together, falling through from conditional continue", () => {
    const d = dialog(["c1"], {
      c1: { kind: "cue", text: "t1", continue: { alts: ["c2"] }, answers: ["al"] },
      c2: { kind: "cue", text: "t2", if: cond },
      al: { kind: "answers", answers: ["a1"] },
      a1: { kind: "answer", text: "x" },
    });
    expect(play(d, []).pending?.options.map((o) => o.id)).toEqual(["c2", "al"]);
    expect(trace(play(d, [1]).steps)).toEqual(["c1", "#1", "a1", "END"]);
  });

  it("lets the user pick success or failure of a check", () => {
    const d = dialog(["k"], {
      k: { kind: "check", tag: "Lore", success: "c1" },
      c1: { kind: "cue", text: "t1" },
    });
    expect(play(d, []).pending?.kind).toBe("check");
    expect(trace(play(d, [0]).steps)).toEqual(["k", "#0", "c1", "END"]);
    expect(trace(play(d, [1]).steps)).toEqual(["k", "#1", "END"]);
  });

  it("plays sequences in order, with play/skip for conditional entries, then the exit", () => {
    const d = dialog(["s"], {
      s: { kind: "sequence", cues: ["c1", "c2", "c3"], exit: "x" },
      c1: { kind: "cue", text: "t1" },
      c2: { kind: "cue", text: "t2", if: cond },
      c3: { kind: "cue", text: "t3" },
      x: { kind: "exit", continue: { alts: ["c4"] } },
      c4: { kind: "cue", text: "t4" },
    });
    expect(play(d, []).pending?.options.map((o) => o.kind)).toEqual(["play", "skip"]);
    expect(trace(play(d, [0]).steps)).toEqual(["s", "c1", "#0", "c2", "c3", "c4", "END"]);
    expect(trace(play(d, [1]).steps)).toEqual(["s", "c1", "#1", "c3", "c4", "END"]);
  });

  it("offers the sequence or an entry's own flow, and returns to the sequence after a branch", () => {
    const d = dialog(["s"], {
      s: { kind: "sequence", cues: ["c1", "c2"] },
      c1: { kind: "cue", text: "t1", continue: { alts: ["b"] } },
      b: { kind: "cue", text: "branch" },
      c2: { kind: "cue", text: "t2" },
    });
    expect(play(d, []).pending?.options.map((o) => o.kind)).toEqual(["resume", "node"]);
    expect(trace(play(d, [0]).steps)).toEqual(["s", "c1", "#0", "c2", "END"]);
    expect(trace(play(d, [1]).steps)).toEqual(["s", "c1", "#1", "b", "c2", "END"]);
  });

  it("follows nested sequences and their exits", () => {
    const d = dialog(["s"], {
      s: { kind: "sequence", cues: ["inner", "c3"] },
      inner: { kind: "sequence", cues: ["c1"], exit: "x" },
      c1: { kind: "cue", text: "t1" },
      x: { kind: "exit", continue: { alts: ["c2"] } },
      c2: { kind: "cue", text: "t2" },
      c3: { kind: "cue", text: "t3" },
    });
    expect(trace(play(d, []).steps)).toEqual(["s", "inner", "c1", "c2", "c3", "END"]);
  });

  it("offers page answers; an answer without next returns to the sequence", () => {
    const d = dialog(["s"], {
      s: { kind: "sequence", cues: ["p", "c2"] },
      p: { kind: "page", cues: ["c1"], answers: ["a1", "a2"] },
      c1: { kind: "cue", text: "t1" },
      a1: { kind: "answer", text: "Continue." },
      a2: { kind: "answer", text: "other", next: { alts: ["c3"] } },
      c2: { kind: "cue", text: "t2" },
      c3: { kind: "cue", text: "t3" },
    });
    expect(trace(play(d, [0]).steps)).toEqual(["s", "p", "a1", "c2", "END"]);
    expect(trace(play(d, [1]).steps)).toEqual(["s", "p", "a2", "c3", "c2", "END"]);
  });

  it("ends the branch at a missing node", () => {
    const d = dialog(["c1"], { c1: { kind: "cue", text: "t1", continue: { alts: ["gone"] } } });
    expect(trace(play(d, []).steps)).toEqual(["c1", "?gone", "END"]);
  });

  it("handles empty dialogs, cycles without choices and invalid paths", () => {
    expect(trace(play({ id: "d", name: "Empty" }, []).steps)).toEqual(["END"]);

    const cycle = dialog(["c1"], { c1: { kind: "cue", continue: { alts: ["c1"] } } });
    expect(trace(play(cycle, []).steps).at(-1)).toBe("LOOP");

    const d = dialog(["c1", "c2"], {
      c1: { kind: "cue", text: "t1", if: cond },
      c2: { kind: "cue", text: "t2" },
    });
    const r = play(d, [5]);
    expect(r.invalid).toBe(true);
    expect(r.used).toBe(0);
    expect(r.pending).not.toBeNull();
  });
});

describe("findPath", () => {
  const d = dialog(["c1"], {
    c1: { kind: "cue", text: "t1", answers: ["al"] },
    al: { kind: "answers", answers: ["a1", "a2"] },
    a1: { kind: "answer", text: "x", next: { alts: ["c2"] } },
    a2: { kind: "answer", text: "y", next: { alts: ["k"] } },
    c2: { kind: "cue", text: "t2", answers: ["al"] },
    k: { kind: "check", success: "p", fail: "c3" },
    p: { kind: "page", cues: ["pc"] },
    pc: { kind: "cue", text: "page text" },
    c3: { kind: "cue", text: "t3" },
  });
  const byKey = (key: string) => (s: Step) => stepTextKeys(s, d.nodes!).includes(key);

  it("finds the shortest path to a text, including page cues", () => {
    expect(findPath(d, byKey("t1"))).toEqual([]);
    expect(findPath(d, byKey("t2"))).toEqual([0]);
    expect(findPath(d, byKey("t3"))).toEqual([1, 1]);
    expect(findPath(d, byKey("page text"))).toEqual([1, 0]);
    const path = findPath(d, byKey("t3"))!;
    expect(trace(play(d, path).steps)).toContain("c3");
  });

  it("returns null for unreachable texts", () => {
    expect(findPath(d, byKey("nowhere"))).toBeNull();
  });
});
