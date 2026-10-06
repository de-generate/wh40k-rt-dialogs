import { describe, expect, it } from "vitest";
import type { IndexEntry } from "../bundle/types";
import { buildTextIndex, defaultFilters, searchDialogs, searchText, snippet } from "./search";

const dialogs: IndexEntry[] = [
  { id: "a", name: "KunradIntro", path: "World/Dialogs/Ch0/KunradIntro", tags: ["Ch0"], chapter: 0, source: "World", type: "Common", nodes: 3, speakers: ["Kunrad"] },
  { id: "b", name: "OldBridge", path: "DLC/DLC1/Bridge/OldBridge", tags: ["DLC1", "Bridge"], source: "DLC1", type: "Common", nodes: 5, deleted: true },
  { id: "c", name: "Nothing", path: "World/Dialogs/Nothing", source: "World", type: "Book" },
  { id: "d", name: "BookIntro", path: "World/Dialogs/BookIntro", source: "World", type: "Book", nodes: 2 },
];

describe("searchDialogs", () => {
  it("never lists deleted or empty dialogs", () => {
    expect(searchDialogs(dialogs, "", defaultFilters).map((d) => d.id)).toEqual(["a", "d"]);
    expect(searchDialogs(dialogs, "bridge", defaultFilters)).toEqual([]);
  });

  it("matches every word against name, path, tags and speakers", () => {
    const all = defaultFilters;
    expect(searchDialogs(dialogs, "kunrad ch0", all).map((d) => d.id)).toEqual(["a"]);
    expect(searchDialogs(dialogs, "", { ...all, chapter: "none" }).map((d) => d.id)).toEqual(["d"]);
    expect(searchDialogs(dialogs, "", { ...all, type: "Book" }).map((d) => d.id)).toEqual(["d"]);
  });
});

describe("searchText", () => {
  const entries = buildTextIndex({
    locale: "enGB",
    dialogs: { a: { k1: "{n}He smiles.{/n} Hello, {mf|sir|madam}." }, b: { k2: "Hello again." } },
  });

  it("searches plain text case-insensitively and applies the filter", () => {
    expect(searchText(entries, "HELLO", () => true, 10).hits.map((h) => h.entry.key)).toEqual(["k1", "k2"]);
    expect(searchText(entries, "sir/madam", () => true, 10).hits.map((h) => h.entry.key)).toEqual(["k1"]);
    expect(searchText(entries, "hello", (d) => d === "b", 10).hits.map((h) => h.entry.key)).toEqual(["k2"]);
    expect(searchText(entries, "hello", () => true, 1).more).toBe(true);
  });

  it("builds snippets around the match", () => {
    expect(snippet("abcdefghij", 4, 2, 2)).toEqual({ before: "…cd", match: "ef", after: "gh…" });
  });
});
