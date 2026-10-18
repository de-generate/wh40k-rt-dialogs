import { For, Match, Show, Switch, createSignal } from "solid-js";
import { bundleState, derived, forgetBundle, loadBundleFile, setTheme, theme } from "../state";
import { themes, type ThemeId } from "../themes/themes";
import { DialogPanel } from "./DialogPanel";
import { Sidebar } from "./Sidebar";

export function App() {
  return (
    <div class="flex h-screen flex-col">
      <Header />
      <Switch>
        <Match when={bundleState().status === "init"}>
          <p class="p-6 text-neutral-500">Opening stored bundle…</p>
        </Match>
        <Match when={bundleState().status === "ready"}>
          <main class="flex min-h-0 flex-1">
            <Sidebar />
            <DialogPanel />
          </main>
        </Match>
        <Match when={true}>
          <LoadScreen />
        </Match>
      </Switch>
    </div>
  );
}

function Header() {
  const manifest = () => derived.bundle()?.manifest;
  return (
    <header class="flex items-center gap-4 border-b border-neutral-800 px-4 py-2 text-sm">
      <h1 class="font-semibold text-neutral-100">Rogue Trader dialog explorer</h1>
      <Show when={manifest()}>
        {(m) => (
          <>
            <span class="text-neutral-500">
              {m().counts.dialogs} dialogs · {m().locales.length} locales · bundle from {m().generatedAt.slice(0, 10)}
            </span>
            <div class="flex-1" />
            <FileButton label="Load another bundle…" />
            <button class="btn" onClick={() => forgetBundle()} title="Remove the bundle from this browser">
              Forget bundle
            </button>
          </>
        )}
      </Show>
      <label class="ml-auto flex items-center gap-1 text-neutral-400">
        Theme
        <select class="input py-0.5" value={theme()} onChange={(e) => setTheme(e.currentTarget.value as ThemeId)}>
          <For each={themes}>{(t) => <option value={t.id}>{t.label}</option>}</For>
        </select>
      </label>
    </header>
  );
}

function FileButton(props: { label: string }) {
  return (
    <label class="btn cursor-pointer">
      {props.label}
      <input
        type="file"
        accept=".zip,application/zip"
        class="hidden"
        onChange={(e) => {
          const file = e.currentTarget.files?.[0];
          e.currentTarget.value = "";
          if (file) loadBundleFile(file);
        }}
      />
    </label>
  );
}

function LoadScreen() {
  const [dragging, setDragging] = createSignal(false);
  const state = () => bundleState();
  return (
    <div class="flex flex-1 items-center justify-center p-6">
      <div
        class={[
          "max-w-lg space-y-4 rounded-lg border-2 border-dashed p-8 text-center",
          dragging() ? "border-sky-500 bg-sky-950/20" : "border-neutral-700",
        ]}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          const file = e.dataTransfer?.files[0];
          if (file) loadBundleFile(file);
        }}
      >
        <Show when={state().status !== "loading"} fallback={<p class="text-neutral-300">Reading bundle…</p>}>
          <p class="text-neutral-200">
            Drop your <span class="font-mono">dialogs-explorer-bundle.zip</span> here, or
          </p>
          <FileButton label="Choose a file…" />
          <p class="text-sm text-neutral-500">
            Create it with the extractor: <span class="font-mono">python -m rt_dialogs output explorer-bundle</span>. The
            file stays in this browser; nothing is uploaded.
          </p>
          <Show when={state().status === "none" && (state() as { error?: string }).error}>
            {(error) => <p class="text-sm text-red-400">{error()}</p>}
          </Show>
        </Show>
      </div>
    </div>
  );
}
