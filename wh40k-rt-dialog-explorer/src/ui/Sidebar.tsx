import { For, Loading, Show, createMemo, createSignal } from "solid-js";
import type { Filters } from "../search/search";
import { isListed, passesFilters, searchDialogs, searchText, snippet } from "../search/search";
import {
  derived,
  filters,
  jumpToText,
  navigate,
  query,
  route,
  searchMode,
  setFilters,
  setQuery,
  setSearchMode,
} from "../state";
import type { JSX } from "@solidjs/web";

const TEXT_HIT_LIMIT = 200;
const MIN_TEXT_QUERY = 3;

export function Sidebar() {
  return (
    <aside class="flex w-96 shrink-0 flex-col border-r border-neutral-800">
      <div class="space-y-2 border-b border-neutral-800 p-3">
        <div class="flex gap-1 text-sm">
          <Tab mode="dialogs">Dialogs</Tab>
          <Tab mode="text">Text ({derived.locale()})</Tab>
        </div>
        <SearchInput />
        <FilterBar />
      </div>
      <div class="flex-1 overflow-y-auto">
        <Show when={searchMode() === "dialogs"} fallback={<TextResults />}>
          <DialogResults />
        </Show>
      </div>
    </aside>
  );
}

function Tab(props: { mode: "dialogs" | "text"; children: JSX.Element }) {
  return (
    <button
      class={[
        "rounded px-2 py-1",
        searchMode() === props.mode ? "bg-neutral-800 text-neutral-100" : "text-neutral-400 hover:text-neutral-200",
      ]}
      onClick={() => {
        setSearchMode(props.mode);
        setTextQuery(query());
      }}
    >
      {props.children}
    </button>
  );
}

// The text search scans every string, so it waits until typing pauses.
const [textQuery, setTextQuery] = createSignal("");
let debounce: ReturnType<typeof setTimeout> | undefined;

function SearchInput() {
  const onInput = (value: string) => {
    setQuery(value);
    clearTimeout(debounce);
    debounce = setTimeout(() => setTextQuery(value), 250);
  };
  return (
    <input
      class="input w-full"
      type="search"
      placeholder={
        searchMode() === "dialogs" ? "Name, tag, path or speaker…" : `Search text (${derived.locale()})…`
      }
      value={query()}
      onInput={(e) => onInput(e.currentTarget.value)}
    />
  );
}

function FilterBar() {
  const index = createMemo(() => (derived.bundle()?.index.dialogs ?? []).filter(isListed));
  const distinct = (values: (string | undefined)[]) => [...new Set(values.filter((v) => v !== undefined))].sort();
  const sources = createMemo(() => distinct(index().map((d) => d.source)));
  const types = createMemo(() => distinct(index().map((d) => d.type)));
  const chapters = createMemo(() =>
    [...new Set(index().flatMap((d) => (d.chapter === undefined ? [] : [d.chapter])))].sort((a, b) => a - b),
  );
  const update = (patch: Partial<Filters>) => setFilters((f) => ({ ...f, ...patch }));

  return (
    <div class="flex flex-wrap items-center gap-2 text-xs text-neutral-400">
      <select class="input py-0.5" value={filters().source} onChange={(e) => update({ source: e.currentTarget.value })}>
        <option value="">All sources</option>
        <For each={sources()}>{(s) => <option value={s}>{s}</option>}</For>
      </select>
      <select class="input py-0.5" value={filters().type} onChange={(e) => update({ type: e.currentTarget.value })}>
        <option value="">All types</option>
        <For each={types()}>{(t) => <option value={t}>{t}</option>}</For>
      </select>
      <select class="input py-0.5" value={filters().chapter} onChange={(e) => update({ chapter: e.currentTarget.value })}>
        <option value="">All chapters</option>
        <For each={chapters()}>{(c) => <option value={String(c)}>Chapter {c}</option>}</For>
        <option value="none">No chapter</option>
      </select>
    </div>
  );
}

function DialogResults() {
  const results = createMemo(() => searchDialogs(derived.bundle()?.index.dialogs ?? [], query(), filters()));
  return (
    <>
      <div class="px-3 py-1 text-xs text-neutral-500">{results().length} dialogs</div>
      <ul>
        <For each={results()}>
          {(d) => (
            <li>
              <button
                class={[
                  "block w-full px-3 py-1.5 text-left hover:bg-neutral-800/70",
                  { "bg-neutral-800": route().dialog === d.id },
                ]}
                onClick={() => navigate(d.id, [])}
              >
                <div class="truncate text-sm text-neutral-200">{d.name}</div>
                <div class="truncate text-xs text-neutral-500">
                  {(d.tags ?? []).join(" · ")}
                  {` · ${d.nodes} nodes`}
                </div>
              </button>
            </li>
          )}
        </For>
      </ul>
    </>
  );
}

function TextResults() {
  const nameById = createMemo(() => new Map((derived.bundle()?.index.dialogs ?? []).map((d) => [d.id, d])));
  const results = createMemo(() => {
    const q = textQuery().trim();
    if (q.length < MIN_TEXT_QUERY) return null;
    const f = filters();
    const byId = nameById();
    const { hits, more } = searchText(derived.textIndex(), q, (id) => {
      const d = byId.get(id);
      return d !== undefined && passesFilters(d, f);
    }, TEXT_HIT_LIMIT);
    return { more, hits: hits.map((hit) => ({ ...hit, snippet: snippet(hit.entry.plain, hit.at, q.length) })) };
  });

  return (
    <Loading fallback={<p class="p-3 text-sm text-neutral-500">Loading {derived.locale()} text…</p>}>
      <Show
        when={results()}
        fallback={<p class="p-3 text-sm text-neutral-500">Type at least {MIN_TEXT_QUERY} characters.</p>}
      >
        {(r) => (
          <>
            <div class="px-3 py-1 text-xs text-neutral-500">
              {r().more ? `First ${TEXT_HIT_LIMIT} matches` : `${r().hits.length} matches`}
            </div>
            <ul>
              <For each={r().hits}>
                {(hit) => {
                  const s = () => hit.snippet;
                  return (
                    <li>
                      <button
                        class="block w-full px-3 py-1.5 text-left hover:bg-neutral-800/70"
                        onClick={() => jumpToText(hit.entry.dialog, hit.entry.key)}
                      >
                        <div class="truncate text-xs text-neutral-500">
                          {nameById().get(hit.entry.dialog)?.name ?? hit.entry.dialog}
                        </div>
                        <div class="text-sm text-neutral-300">
                          {s().before}
                          <mark class="rounded bg-sky-800/70 px-0.5 text-neutral-100">{s().match}</mark>
                          {s().after}
                        </div>
                      </button>
                    </li>
                  );
                }}
              </For>
            </ul>
          </>
        )}
      </Show>
    </Loading>
  );
}
