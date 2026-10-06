import { Errored, For, Loading, Match, Show, Switch, createEffect, createMemo, isPending, onSettled } from "solid-js";
import type { JSX } from "@solidjs/web";
import type { Dialog, DialogNode, IndexEntry } from "../bundle/types";
import type { ChoicePoint, Option, PlayResult, Step } from "../player/engine";
import { stepTextKeys } from "../player/engine";
import {
  derived,
  gender,
  highlight,
  navigate,
  notice,
  playerName,
  route,
  setGender,
  setLocale,
  setPlayerName,
  setShowComments,
  showComments,
  type Gender,
} from "../state";
import { Badge, Comment, CondLine, ActionList, NodeBadges, NodeDetails } from "./meta";
import { NodeText } from "./text";

export function DialogPanel() {
  return (
    <section class="flex min-w-0 flex-1 flex-col">
      <Show
        when={route().dialog}
        fallback={<p class="p-6 text-neutral-500">Pick a dialog on the left.</p>}
      >
        <Errored fallback={(err) => <p class="p-6 text-red-400">Could not open this dialog: {String(err())}</p>}>
          <Loading fallback={<p class="p-6 text-neutral-500">Loading dialog…</p>}>
            <DialogView />
          </Loading>
        </Errored>
      </Show>
    </section>
  );
}

function DialogView() {
  let scroller: HTMLDivElement | undefined;

  // Keep the newest step in view; after a search jump, the highlighted text instead.
  createEffect(
    () => [derived.result(), highlight()] as const,
    ([, key]) => {
      requestAnimationFrame(() => {
        const target = key ? scroller?.querySelector("[data-highlight]") : null;
        if (target) target.scrollIntoView({ block: "center" });
        else scroller?.scrollTo({ top: scroller.scrollHeight });
      });
    },
  );

  return (
    <Show when={derived.dialog()}>
      {(d) => (
        <>
          <Toolbar />
          <Show when={notice()}>
            <p class="border-b border-neutral-800 bg-amber-950/40 px-4 py-2 text-sm text-amber-200">{notice()}</p>
          </Show>
          <div ref={scroller} class="flex-1 overflow-y-auto px-6 py-4">
            <div class="mx-auto max-w-3xl">
              <DialogHeader dialog={d()} entry={derived.indexEntry()} />
              <Show when={derived.result()}>{(r) => <Transcript dialog={d()} result={r()} />}</Show>
            </div>
          </div>
        </>
      )}
    </Show>
  );
}

function Toolbar() {
  const path = () => route().path.slice(0, derived.result()?.used ?? 0);
  const id = () => route().dialog!;
  const locales = () => derived.bundle()?.manifest.locales ?? [];

  // Keys: 1–9 pick an option, Backspace goes back one step.
  onSettled(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (t.closest("input, select, textarea") || e.ctrlKey || e.metaKey || e.altKey) return;
      const pending = derived.result()?.pending;
      if (/^[1-9]$/.test(e.key) && pending && Number(e.key) <= pending.options.length) {
        navigate(id(), [...path(), Number(e.key) - 1]);
      } else if (e.key === "Backspace" && path().length > 0) {
        navigate(id(), path().slice(0, -1));
      } else return;
      e.preventDefault();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  });

  return (
    <div class="flex flex-wrap items-center gap-2 border-b border-neutral-800 px-4 py-2 text-sm">
      <button class="btn" disabled={path().length === 0} onClick={() => navigate(id(), path().slice(0, -1))} title="Backspace">
        ← Back
      </button>
      <button class="btn" disabled={path().length === 0} onClick={() => navigate(id(), [])}>
        Reset
      </button>
      <span class="text-neutral-500">
        {path().length} choice{path().length === 1 ? "" : "s"}
      </span>
      <div class="flex-1" />
      <Show when={isPending(() => derived.strings())}>
        <span class="text-neutral-500">loading text…</span>
      </Show>
      <label class="flex items-center gap-1 text-neutral-400" title="Language of the dialog text and of full-text search">
        Text
        <select class="input py-0.5" value={derived.locale() ?? ""} onChange={(e) => setLocale(e.currentTarget.value)}>
          <For each={locales()}>{(l) => <option value={l}>{l}</option>}</For>
        </select>
      </label>
      <label class="flex items-center gap-1 text-neutral-400" title="Picks the {mf|…} variant; none shows both">
        Gender
        <select class="input py-0.5" value={gender()} onChange={(e) => setGender(e.currentTarget.value as Gender)}>
          <option value="">none</option>
          <option value="male">male</option>
          <option value="female">female</option>
        </select>
      </label>
      <label class="flex items-center gap-1 text-neutral-400" title="Replaces ‹name›; empty keeps the placeholder">
        Name
        <input
          class="input w-28 py-0.5"
          value={playerName()}
          placeholder="‹name›"
          onInput={(e) => setPlayerName(e.currentTarget.value)}
        />
      </label>
      <label class="flex items-center gap-1 text-neutral-400">
        <input type="checkbox" checked={showComments()} onChange={(e) => setShowComments(e.currentTarget.checked)} />
        Comments
      </label>
    </div>
  );
}

function DialogHeader(props: { dialog: Dialog; entry: IndexEntry | null }) {
  return (
    <header class="mb-6 space-y-1 border-b border-neutral-800 pb-4">
      <h2 class="flex flex-wrap items-center gap-2 text-lg font-semibold text-neutral-100">
        {props.dialog.name}
        <Show when={props.dialog.deleted}>
          <Badge class="bg-red-950 text-red-300">deleted</Badge>
        </Show>
      </h2>
      <Show when={props.entry}>
        {(e) => (
          <div class="flex flex-wrap items-center gap-1 text-xs text-neutral-400">
            <span class="font-mono">{e().path}</span>
            <Badge>{e().source}</Badge>
            <Badge>{e().type}</Badge>
            <Show when={e().chapter !== undefined}>
              <Badge>chapter {e().chapter}</Badge>
            </Show>
            <Badge>{e().nodes ?? 0} nodes</Badge>
          </div>
        )}
      </Show>
      <CondLine label="starts if" c={props.dialog.if} />
      <ActionList actions={props.dialog.actions} />
      <Comment text={props.dialog.comment} />
    </header>
  );
}

function Transcript(props: { dialog: Dialog; result: PlayResult }) {
  const nodes = () => props.dialog.nodes ?? {};
  const visited = createMemo(() => new Set(props.result.steps.flatMap((s) => (s.kind === "node" ? [s.id] : []))));
  return (
    <div class="space-y-3">
      {/* Index-keyed: a longer path replays the same leading steps, so their rows are reused. */}
      <For each={props.result.steps} keyed={false}>
        {(step) => <StepView step={step()} nodes={nodes()} />}
      </For>
      <Show when={props.result.invalid}>
        <p class="text-sm text-amber-300">The rest of the path in the URL doesn't match this dialog and was ignored.</p>
      </Show>
      <Show when={props.result.pending}>
        {(p) => <ChoiceView point={p()} nodes={nodes()} visited={visited()} />}
      </Show>
    </div>
  );
}

function textKey(node: DialogNode): string | undefined {
  return node.kind === "cue" || node.kind === "answer" ? node.text : undefined;
}

function speakerName(node: DialogNode): string {
  if (node.kind !== "cue") return "";
  return node.speaker ?? (node.narrator ? "Narrator" : "NPC");
}

function StepView(props: { step: Step; nodes: Record<string, DialogNode> }) {
  const highlighted = () => {
    const key = highlight();
    return key !== null && stepTextKeys(props.step, props.nodes).includes(key);
  };
  return (
    <div data-highlight={highlighted() || undefined} class={{ "rounded ring-1 ring-sky-500/70 ring-offset-4 ring-offset-neutral-950": highlighted() }}>
      <Switch>
        <Match when={props.step.kind === "node" && props.step}>
          {(s) => <NodeStep id={s().id} node={s().node} nodes={props.nodes} />}
        </Match>
        <Match when={props.step.kind === "choice" && props.step}>
          {(s) => (
            <div class="text-xs text-neutral-500">
              ↳ {optionSummary(s().point.options[s().index], props.nodes)}
            </div>
          )}
        </Match>
        <Match when={props.step.kind === "missing" && props.step}>
          {(s) => <div class="text-sm text-red-400">Missing node <span class="font-mono">{s().id}</span>; the branch ends here.</div>}
        </Match>
        <Match when={props.step.kind === "end"}>
          <div class="py-4 text-center text-sm text-neutral-500">— End of dialog —</div>
        </Match>
        <Match when={props.step.kind === "loop"}>
          <div class="text-sm text-amber-300">The dialog loops here without any choice; stopped.</div>
        </Match>
      </Switch>
    </div>
  );
}

function NodeStep(props: { id: string; node: DialogNode; nodes: Record<string, DialogNode> }) {
  const n = () => props.node;
  return (
    <div class={{ "opacity-60": !!n().deleted }}>
      <Switch>
        <Match when={n().kind === "cue" && n()}>
          {(c) => (
            <div>
              <div class="flex flex-wrap items-center gap-1">
                <span class="text-xs font-semibold text-sky-400/90">{speakerName(c())}</span>
                <NodeBadges node={c()} />
              </div>
              <div class="leading-relaxed">
                <NodeText textKey={textKey(c())} />
              </div>
              <NodeDetails node={c()} />
            </div>
          )}
        </Match>
        <Match when={n().kind === "answer" && n()}>
          {(a) => (
            <div class="ml-8 border-l-2 border-amber-600/60 pl-3">
              <div class="flex flex-wrap items-center gap-1">
                <span class="text-xs font-semibold text-amber-500/90">You</span>
                <NodeBadges node={a()} />
              </div>
              <div class="text-amber-100">
                <NodeText textKey={textKey(a())} />
              </div>
              <NodeDetails node={a()} />
            </div>
          )}
        </Match>
        <Match when={n().kind === "check" && n()}>
          {(k) => (
            <div class="text-sm">
              <span class="text-indigo-300">Check</span> <NodeBadges node={k()} />
              <NodeDetails node={k()} />
            </div>
          )}
        </Match>
        <Match when={n().kind === "sequence" && n()}>
          {(s) => (
            <div class="text-xs text-neutral-500">
              ▸ sequence <NodeBadges node={s()} />
              <NodeDetails node={s()} />
            </div>
          )}
        </Match>
        <Match when={n().kind === "page" && n()}>
          {(p) => <PageStep node={p()} nodes={props.nodes} />}
        </Match>
      </Switch>
    </div>
  );
}

function PageStep(props: { node: DialogNode; nodes: Record<string, DialogNode> }) {
  const cues = () => (props.node.kind === "page" ? (props.node.cues ?? []) : []);
  return (
    <div class="rounded border border-neutral-800 bg-neutral-900/60 p-3">
      <div class="mb-1 flex items-center gap-1 text-xs text-neutral-500">
        page <NodeBadges node={props.node} />
      </div>
      <NodeDetails node={props.node} />
      <div class="space-y-2">
        <For each={cues()}>
          {(id) => (
            <Show
              when={props.nodes[id]}
              fallback={<div class="text-sm text-red-400">Missing node <span class="font-mono">{id}</span></div>}
            >
              {(c) => (
                <div class={{ "opacity-60": !!c().deleted }}>
                  <Show when={c().kind === "cue" && c()} fallback={<NodeStep id={id} node={c()} nodes={props.nodes} />}>
                    {(cue) => (
                      <>
                        <NodeBadges node={cue()} />
                        <div class="leading-relaxed">
                          <NodeText textKey={textKey(cue())} />
                        </div>
                        <NodeDetails node={cue()} />
                      </>
                    )}
                  </Show>
                </div>
              )}
            </Show>
          )}
        </For>
      </div>
    </div>
  );
}

// ---- Choices

const kindLabel: Record<DialogNode["kind"], string> = {
  cue: "Cue",
  answers: "Answer list",
  answer: "Answer",
  check: "Check",
  sequence: "Sequence",
  exit: "Sequence exit",
  page: "Page",
};

function optionSummary(o: Option, nodes: Record<string, DialogNode>): string {
  switch (o.kind) {
    case "end":
      return o.resumes ? "no option passes: back to the sequence" : "no option passes: dialog ends";
    case "resume":
      return "next in sequence";
    case "success":
      return "check succeeded";
    case "fail":
      return "check failed";
    case "play":
      return "played the conditional entry";
    case "skip":
      return "skipped the conditional entry";
    case "node": {
      const node = o.id ? nodes[o.id] : undefined;
      return node ? `took the ${kindLabel[node.kind].toLowerCase()} alternative` : "went to a missing node";
    }
  }
}

function ChoiceView(props: { point: ChoicePoint; nodes: Record<string, DialogNode>; visited: Set<string> }) {
  const path = () => route().path.slice(0, derived.result()?.used ?? 0);
  const title = () =>
    ({
      alternatives: "Where does it go on?",
      answers: "Answers",
      check: "Check result",
      entry: "Conditional sequence entry",
    })[props.point.kind];
  return (
    <div class="mt-6 border-t border-neutral-800 pt-4">
      <div class="mb-2 text-xs tracking-wide text-neutral-500 uppercase">{title()}</div>
      <ol class="space-y-1">
        <For each={props.point.options}>
          {(o, i) => (
            <li>
              <button
                class={[
                  "flex w-full gap-3 rounded px-3 py-2 text-left hover:bg-neutral-800/80",
                  { "opacity-50": o.id !== undefined && !!props.nodes[o.id]?.once && props.visited.has(o.id) },
                ]}
                onClick={() => navigate(route().dialog!, [...path(), i()])}
              >
                <span class="w-4 shrink-0 text-right text-neutral-500">{i() + 1}</span>
                <span class="min-w-0 flex-1">
                  <OptionBody option={o} nodes={props.nodes} />
                </span>
              </button>
            </li>
          )}
        </For>
      </ol>
    </div>
  );
}

function OptionBody(props: { option: Option; nodes: Record<string, DialogNode> }): JSX.Element {
  const o = () => props.option;
  const node = () => (o().id ? props.nodes[o().id!] : undefined);
  return (
    <Switch>
      <Match when={o().kind === "end"}>
        <span class="text-neutral-400">
          {o().fallthrough ? "If nothing above passes: " : ""}
          {o().resumes ? "back to the sequence" : "end of dialog"}
        </span>
      </Match>
      <Match when={o().kind === "resume"}>
        <span class="text-neutral-400">Next in sequence</span>
      </Match>
      <Match when={o().kind === "skip"}>
        <span class="text-neutral-400">Skip this entry</span>
      </Match>
      <Match when={o().kind === "success" || o().kind === "fail"}>
        <span class={o().kind === "success" ? "text-emerald-300" : "text-red-300"}>
          {o().kind === "success" ? "Success" : "Failure"}
        </span>
        <Show when={!o().id}>
          <span class="text-neutral-500"> (branch ends)</span>
        </Show>
      </Match>
      <Match when={o().id && !node()}>
        <span class="text-red-400">Missing node</span>
      </Match>
      <Match when={node()}>
        {(n) => (
          <div>
            <Show when={o().kind === "play"}>
              <span class="text-neutral-400">Play: </span>
            </Show>
            <Show when={o().random}>
              <Badge class="mr-1 bg-teal-950 text-teal-200">random</Badge>
            </Show>
            <NodePreview node={n()} nodes={props.nodes} />
          </div>
        )}
      </Match>
    </Switch>
  );
}

/** What an option leads to, in one block. */
function NodePreview(props: { node: DialogNode; nodes: Record<string, DialogNode> }) {
  const n = () => props.node;
  return (
    <div class={{ "opacity-60": !!n().deleted }}>
      <div class="flex flex-wrap items-center gap-1">
        <Show when={n().kind !== "answer"}>
          <span class="text-xs font-semibold text-neutral-400">
            {n().kind === "cue" ? speakerName(n()) : kindLabel[n().kind]}
          </span>
        </Show>
        <NodeBadges node={n()} />
      </div>
      <Switch>
        <Match when={n().kind === "cue" && n()}>
          {(c) => <NodeText textKey={textKey(c())} />}
        </Match>
        <Match when={n().kind === "answer" && n()}>
          {(a) => (
            <span class="text-amber-100">
              <NodeText textKey={textKey(a())} />
            </span>
          )}
        </Match>
        <Match when={n().kind === "answers" && n()}>
          {(l) => (
            <ul class="list-inside list-disc text-sm text-neutral-400">
              <For each={l().kind === "answers" ? ((l() as { answers?: string[] }).answers ?? []) : []}>
                {(id) => {
                  const a = () => props.nodes[id];
                  return (
                    <li>
                      <NodeText textKey={a() ? textKey(a()) : undefined} />
                    </li>
                  );
                }}
              </For>
            </ul>
          )}
        </Match>
        <Match when={(n().kind === "sequence" || n().kind === "page") && n()}>
          {(s) => {
            const first = () => {
              const cues = s().kind === "sequence" || s().kind === "page" ? (s() as { cues?: string[] }).cues : undefined;
              const c = cues?.[0] ? props.nodes[cues[0]] : undefined;
              return c?.kind === "cue" ? c.text : undefined;
            };
            return (
              <Show when={first()}>
                <div class="text-sm text-neutral-300">
                  <NodeText textKey={first()} /> …
                </div>
              </Show>
            );
          }}
        </Match>
      </Switch>
      <NodeDetails node={n()} />
    </div>
  );
}
