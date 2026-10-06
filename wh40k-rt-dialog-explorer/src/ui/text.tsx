import { For, Match, Show, Switch } from "solid-js";
import { derived, gender, playerName, route } from "../state";
import { parseMarkup } from "../text/markup";

/** Game text with inline markup. Gender and name settings pick `{mf|…}` variants and fill `{name}`. */
export function RichText(props: { text: string }) {
  return (
    <For each={parseMarkup(props.text)}>
      {(s) => (
        <Switch>
          <Match when={s.t === "break"}>
            <br />
          </Match>
          <Match when={s.t === "text" && s}>
            {(t) => <span class={{ "text-neutral-400 italic": t().narration }}>{t().text}</span>}
          </Match>
          <Match when={s.t === "variants" && s.tag === "mf" && gender() !== "" && s}>
            {(v) => (
              <span class={{ "text-neutral-400 italic": v().narration }}>
                {v().options[gender() === "male" ? 0 : 1] ?? ""}
              </span>
            )}
          </Match>
          <Match when={s.t === "placeholder" && s.name === "name" && playerName().trim() !== "" && s}>
            {(p) => <span class={{ "text-neutral-400 italic": p().narration }}>{playerName().trim()}</span>}
          </Match>
          <Match when={s.t === "variants" && s}>
            {(v) => (
              <span
                class={["rounded bg-neutral-800 px-1 text-sky-300", { italic: v().narration }]}
                title={v().tag === "mf" ? "male / female" : `variants ({${v().tag}|…})`}
              >
                {v().options.map((o) => o || "∅").join(" / ")}
              </span>
            )}
          </Match>
          <Match when={s.t === "placeholder" && s}>
            {(p) => <span class="text-sky-300">‹{p().name}›</span>}
          </Match>
        </Switch>
      )}
    </For>
  );
}

/** The text of a node of the current dialog, in the active locale. */
export function NodeText(props: { textKey?: string }) {
  const text = () => {
    const key = props.textKey;
    const id = route().dialog;
    return key && id ? derived.strings()?.dialogs[id]?.[key] : undefined;
  };
  const fallback = () => (props.textKey ? derived.fallbackKeys().has(props.textKey) : false);
  return (
    <Show when={props.textKey} fallback={<span class="text-neutral-500 italic">(no text)</span>}>
      <Show when={text()} fallback={<span class="text-red-400 italic">(missing text)</span>}>
        {(t) => (
          <>
            <RichText text={t()} />
            <Show when={fallback()}>
              <span class="ml-1 text-xs text-neutral-500" title="Not translated; shown from the fallback locale">
                [{derived.bundle()?.manifest.fallbackLocale}]
              </span>
            </Show>
          </>
        )}
      </Show>
    </Show>
  );
}
