// App-wide state. Module-scope signals are globals; derived values live in one detached root.

import { createMemo, createRoot, createSignal } from "solid-js";
import { Bundle, BundleError } from "./bundle/bundle";
import { clearStoredBundle, loadStoredBundle, storeBundle } from "./bundle/storage";
import type { Dialog } from "./bundle/types";
import { findPath, play, stepTextKeys } from "./player/engine";
import { buildTextIndex, defaultFilters, type Filters } from "./search/search";

// ---- Bundle

export type BundleState =
  | { status: "init" }
  | { status: "none"; error?: string }
  | { status: "loading" }
  | { status: "ready"; bundle: Bundle };

const [bundleState, setBundleState] = createSignal<BundleState>({ status: "init" });
export { bundleState };

function errorMessage(e: unknown): string {
  if (e instanceof BundleError) return e.message;
  console.error(e);
  return `Could not read the bundle: ${e instanceof Error ? e.message : String(e)}`;
}

export async function initBundle() {
  try {
    const blob = await loadStoredBundle();
    if (!blob) return setBundleState({ status: "none" });
    setBundleState({ status: "ready", bundle: await Bundle.open(blob) });
  } catch (e) {
    setBundleState({ status: "none", error: `The stored bundle can't be used. ${errorMessage(e)}` });
  }
}

export async function loadBundleFile(file: File) {
  const previous = bundleState();
  setBundleState({ status: "loading" });
  try {
    const bundle = await Bundle.open(file);
    await storeBundle(file);
    setBundleState({ status: "ready", bundle });
  } catch (e) {
    // A failed replacement keeps the bundle that was loaded before.
    setBundleState(previous.status === "ready" ? previous : { status: "none", error: errorMessage(e) });
    if (previous.status === "ready") alertError(errorMessage(e));
  }
}

export async function forgetBundle() {
  await clearStoredBundle();
  setBundleState({ status: "none" });
  navigate(null, []);
}

// ---- Notices (transient messages at the top of the dialog panel)

const [notice, setNotice] = createSignal<string | null>(null);
export { notice, setNotice };

function alertError(message: string) {
  setNotice(message);
}

// ---- Route: #/<dialogId>/<choice>.<choice>…

export interface Route {
  dialog: string | null;
  path: number[];
}

function parseHash(): Route {
  const [dialog, path] = location.hash.replace(/^#\/?/, "").split("/");
  return {
    dialog: dialog || null,
    path: path ? path.split(".").map(Number).filter((n) => Number.isInteger(n) && n >= 0) : [],
  };
}

const [route, setRoute] = createSignal<Route>(parseHash(), {
  equals: (a, b) => a.dialog === b.dialog && a.path.join(".") === b.path.join("."),
});
export { route };
window.addEventListener("hashchange", () => setRoute(parseHash()));

/** Text key to highlight in the transcript (set when jumping to a search hit). */
const [highlight, setHighlight] = createSignal<string | null>(null);
export { highlight };

export function navigate(dialog: string | null, path: number[], highlightKey: string | null = null) {
  setHighlight(highlightKey);
  setNotice(null);
  const hash = dialog ? `#/${dialog}${path.length ? "/" + path.join(".") : ""}` : "";
  if (hash !== location.hash) {
    if (hash) location.hash = hash;
    else history.pushState(null, "", location.pathname + location.search);
  }
  setRoute(parseHash());
}

// ---- Display settings, remembered in localStorage. They change only how text is shown, never the dialog logic.

function persisted<T extends string | boolean>(key: string, initial: T) {
  let stored: T = initial;
  try {
    const raw = localStorage.getItem(key);
    if (raw !== null) {
      // The first version stored the locale as a bare string.
      stored = typeof initial === "string" && !raw.startsWith('"') ? (raw as T) : (JSON.parse(raw) as T);
    }
  } catch {
    // Unavailable or corrupt; use the default.
  }
  const [value, setValue] = createSignal<T>(stored as Exclude<T, Function>);
  const set = (next: T) => {
    setValue(() => next);
    try {
      localStorage.setItem(key, JSON.stringify(next));
    } catch {
      // Not persisted; fine.
    }
  };
  return [value, set] as const;
}

/** Wanted locale; `derived.locale` falls back if the bundle lacks it. Affects dialog text and full-text search. */
const [preferredLocale, setLocale] = persisted<string>("locale", "enGB");
/** Player gender for `{mf|…}` text; "" shows both variants. */
export type Gender = "" | "male" | "female";
const [gender, setGender] = persisted<Gender>("gender", "");
/** Player name for `{name}`; "" shows the placeholder. */
const [playerName, setPlayerName] = persisted<string>("playerName", "");
const [showComments, setShowComments] = persisted<boolean>("showComments", false);
export { setLocale, gender, setGender, playerName, setPlayerName, showComments, setShowComments };

// ---- Search input (kept here so it survives re-renders of the sidebar)

export type SearchMode = "dialogs" | "text";
const [searchMode, setSearchMode] = createSignal<SearchMode>("dialogs");
const [query, setQuery] = createSignal("");
const [filters, setFilters] = createSignal<Filters>(defaultFilters);
export { searchMode, setSearchMode, query, setQuery, filters, setFilters };

// ---- Derived

export const derived = createRoot(() => {
  const bundle = createMemo(() => {
    const s = bundleState();
    return s.status === "ready" ? s.bundle : null;
  });

  const locale = createMemo(() => {
    const b = bundle();
    if (!b) return null;
    const { locales, fallbackLocale } = b.manifest;
    const wanted = preferredLocale();
    if (locales.includes(wanted)) return wanted;
    return locales.includes(fallbackLocale) ? fallbackLocale : (locales[0] ?? null);
  });

  const strings = createMemo(async () => {
    const b = bundle();
    const l = locale();
    return b && l ? b.strings(l) : null;
  });

  const fallbackKeys = createMemo(() => new Set(strings()?.fallback ?? []));

  const textIndex = createMemo(
    () => {
      const s = strings();
      return s ? buildTextIndex(s) : [];
    },
    { lazy: true },
  );

  const dialog = createMemo(async (): Promise<Dialog | null> => {
    const b = bundle();
    const id = route().dialog;
    return b && id ? b.dialog(id) : null;
  });

  const indexEntry = createMemo(() => {
    const id = route().dialog;
    return bundle()?.index.dialogs.find((d) => d.id === id) ?? null;
  });

  const result = createMemo(() => {
    const d = dialog();
    return d ? play(d, route().path) : null;
  });

  return { bundle, locale, strings, fallbackKeys, textIndex, dialog, indexEntry, result };
});

/** Opens a dialog at the shortest path that shows the given text key. */
export async function jumpToText(dialogId: string, key: string) {
  const b = derived.bundle();
  if (!b) return;
  const d = await b.dialog(dialogId);
  const nodes = d.nodes ?? {};
  const path = findPath(d, (step) => stepTextKeys(step, nodes).includes(key));
  navigate(dialogId, path ?? [], key);
  if (!path) setNotice("No path from the start reaches this text within the search limits; showing the start.");
}
