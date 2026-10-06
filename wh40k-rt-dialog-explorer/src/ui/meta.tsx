import { For, Show } from "solid-js";
import type { JSX } from "@solidjs/web";
import { showComments } from "../state";
import { isGroup, type Actions, type Condition, type ConditionGroup, type DialogNode, type SoulMark } from "../bundle/types";

/** A condition as readable text. Conditions are labels only; they never hide anything. */
export function Cond(props: { c: Condition; nested?: boolean }): JSX.Element {
  return (
    <Show
      when={isGroup(props.c) && props.c}
      fallback={<Leaf c={props.c as Exclude<Condition, ConditionGroup>} />}
    >
      {(g) => (
        <span>
          {g().not ? "not " : ""}
          {props.nested || g().not ? "(" : ""}
          <For each={g().items}>
            {(item, i) => (
              <>
                <Show when={i() > 0}>
                  <span class="text-neutral-500"> {g().op} </span>
                </Show>
                <Cond c={item} nested={g().items.length > 1} />
              </>
            )}
          </For>
          {props.nested || g().not ? ")" : ""}
        </span>
      )}
    </Show>
  );
}

function Leaf(props: { c: Exclude<Condition, ConditionGroup> }) {
  return (
    <Show when={props.c.type === "False"} fallback={<span>{props.c.label}</span>}>
      <Badge class="bg-red-950 text-red-300">{props.c.not ? "always" : "never"}</Badge>
    </Show>
  );
}

export function Badge(props: { class?: string; title?: string; children: JSX.Element }) {
  return (
    <span class={["rounded px-1 text-xs", props.class ?? "bg-neutral-800 text-neutral-300"]} title={props.title}>
      {props.children}
    </span>
  );
}

function CondLine(props: { label: string; c?: ConditionGroup }) {
  return (
    <Show when={props.c}>
      {(c) => (
        <div class="text-xs text-amber-200/80">
          <span class="text-neutral-500">{props.label}: </span>
          <Cond c={c()} />
        </div>
      )}
    </Show>
  );
}

function soulMarkText(s: SoulMark): string[] {
  const out: string[] = [];
  if (s.shift) out.push(`${s.shift.dir} ${s.shift.value !== undefined ? `+${s.shift.value}` : "shift"}`);
  if (s.requires) {
    const r = s.requires;
    out.push(`requires ${r.dir} ${r.value !== undefined ? r.value : r.rank !== undefined ? `rank ${r.rank}` : ""}`.trim());
  }
  return out;
}

export function ActionList(props: { actions?: Actions }) {
  return (
    <For each={Object.entries(props.actions ?? {}).filter(([, list]) => list.length > 0)}>
      {([event, list]) => (
        <div class="text-xs text-neutral-500">
          on {event}: <span class="font-mono text-neutral-400">{list.join("; ")}</span>
        </div>
      )}
    </For>
  );
}

/** Designer comment; hidden unless the setting is on. */
export function Comment(props: { text?: string }) {
  return (
    <Show when={showComments() && props.text}>
      <div class="text-xs whitespace-pre-line text-emerald-300/70 italic" title="Designer comment">
        // {props.text}
      </div>
    </Show>
  );
}

/** Badges for a node: once, check tags, soul marks, deleted, … */
export function NodeBadges(props: { node: DialogNode }) {
  const n = () => props.node;
  return (
    <>
      <Show when={n().deleted}>
        <Badge class="bg-red-950 text-red-300">deleted</Badge>
      </Show>
      <Show when={n().once}>
        <Badge title={n().once === "always" ? "Shown only once" : "Shown once per conversation"}>
          once{n().once === "dialog" ? " per conversation" : ""}
        </Badge>
      </Show>
      <Show when={"tag" in n() && (n() as { tag?: string }).tag}>
        {(tag) => <Badge class="bg-indigo-950 text-indigo-200">{tag()}</Badge>}
      </Show>
      <Show when={n().kind === "check" && (n() as { hidden?: boolean }).hidden}>
        <Badge>hidden</Badge>
      </Show>
      <Show when={"by" in n() && (n() as { by?: string }).by}>
        {(by) => <Badge>by {by()}</Badge>}
      </Show>
      <For each={"fakeTags" in n() ? ((n() as { fakeTags?: string[] }).fakeTags ?? []) : []}>
        {(t) => <Badge class="bg-neutral-800 text-neutral-400 line-through" title="Fake check tag">{t}</Badge>}
      </For>
      <For each={n().soulMark ? soulMarkText(n().soulMark!) : []}>
        {(t) => <Badge class="bg-purple-950 text-purple-200">{t}</Badge>}
      </For>
    </>
  );
}

/** Conditions, actions and comment below a node. */
export function NodeDetails(props: { node: DialogNode }) {
  const n = () => props.node;
  return (
    <>
      <CondLine label="if" c={n().if} />
      <CondLine label="shown if" c={n().kind === "answer" ? (n() as { show?: ConditionGroup }).show : undefined} />
      <CondLine label="selectable if" c={n().kind === "answer" ? (n() as { select?: ConditionGroup }).select : undefined} />
      <ActionList actions={n().actions} />
      <Comment text={n().comment} />
    </>
  );
}

export { CondLine };
