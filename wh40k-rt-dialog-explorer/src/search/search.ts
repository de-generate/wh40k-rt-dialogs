import type { IndexEntry, Strings } from "../bundle/types";
import { plainText } from "../text/markup";

export interface Filters {
  source: string; // "" = any
  type: string;
  chapter: string; // "" = any, "none" = without chapter, else the number
}

export const defaultFilters: Filters = { source: "", type: "", chapter: "" };

/** Deleted and empty dialogs have nothing worth exploring; they are never listed. */
export function isListed(d: IndexEntry): boolean {
  return !d.deleted && !!d.nodes;
}

export function passesFilters(d: IndexEntry, f: Filters): boolean {
  if (!isListed(d)) return false;
  if (f.source && d.source !== f.source) return false;
  if (f.type && d.type !== f.type) return false;
  if (f.chapter === "none") return d.chapter === undefined;
  if (f.chapter && d.chapter !== Number(f.chapter)) return false;
  return true;
}

function haystack(d: IndexEntry): string {
  return [d.name, d.path, ...(d.tags ?? []), ...(d.speakers ?? [])].join("\n").toLowerCase();
}

/** Dialogs whose name, path, tags or speakers contain every word of the query. */
export function searchDialogs(dialogs: IndexEntry[], query: string, f: Filters): IndexEntry[] {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean);
  return dialogs.filter((d) => {
    if (!passesFilters(d, f)) return false;
    if (words.length === 0) return true;
    const h = haystack(d);
    return words.every((w) => h.includes(w));
  });
}

export interface TextEntry {
  dialog: string;
  key: string;
  plain: string;
  lower: string;
}

export interface TextHit {
  entry: TextEntry;
  at: number; // match position in entry.plain
}

/** Flattens a strings file for full-text search. */
export function buildTextIndex(strings: Strings): TextEntry[] {
  const out: TextEntry[] = [];
  for (const [dialog, group] of Object.entries(strings.dialogs)) {
    for (const [key, text] of Object.entries(group)) {
      const plain = plainText(text);
      out.push({ dialog, key, plain, lower: plain.toLowerCase() });
    }
  }
  return out;
}

export function searchText(
  entries: TextEntry[],
  query: string,
  allow: (dialog: string) => boolean,
  limit: number,
): { hits: TextHit[]; more: boolean } {
  const q = query.trim().toLowerCase();
  const hits: TextHit[] = [];
  if (!q) return { hits, more: false };
  for (const entry of entries) {
    const at = entry.lower.indexOf(q);
    if (at < 0 || !allow(entry.dialog)) continue;
    if (hits.length === limit) return { hits, more: true };
    hits.push({ entry, at });
  }
  return { hits, more: false };
}

/** A window of text around a match. */
export function snippet(plain: string, at: number, length: number, radius = 60) {
  const start = Math.max(0, at - radius);
  const end = Math.min(plain.length, at + length + radius);
  return {
    before: (start > 0 ? "…" : "") + plain.slice(start, at),
    match: plain.slice(at, at + length),
    after: plain.slice(at + length, end) + (end < plain.length ? "…" : ""),
  };
}
