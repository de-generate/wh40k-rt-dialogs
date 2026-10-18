# Notes for agents: explorer

Static web app that plays the extractor's explorer bundle. The bundle format is owned by the extractor
(`../wh40k-rt-dialog-extractor/EXPLORER_BUNDLE.md`); follow it, and update `src/bundle/types.ts` and
`SUPPORTED_VERSION` when its version changes.

Stack: Solid 2.0 (release candidate) + TypeScript 7 + Vite 8 + Tailwind 4, `@zip.js/zip.js` for random access to the
zip, `idb-keyval` for storage, Vitest for tests. Run `pnpm test` and `pnpm build` (includes `tsc`) before
finishing.

## Solid 2 is not Solid 1

Read `node_modules/solid-js/CHEATSHEET.md` before writing components. The traps that matter here:

* Prefer `@solidjs/web` for `render` and the `JSX` type over `solid-js`.
* `createEffect(compute, apply)` has two arguments; prefer `onSettled` for component setup and teardown.
* Prefer passing values (`x={sig()}`) over accessors, and `props.x` over destructuring.
* Prefer `class={{ … }}` / arrays over `classList` or string concatenation; object values must be booleans.
* Async memos (`derived.strings`, `derived.dialog`) suspend under `<Loading>`; keep reads of them inside a boundary.
* Dev mode prints diagnostics (`WIDE_SCOPE_DEPS`, `HUGE_FAN_OUT`, …) with repair guides in
  `node_modules/solid-js/skills/`. Prefer fixing them over ignoring them.

## Layout

| Path | Purpose |
|---|---|
| `src/bundle/` | Bundle types (spec §3–7), zip reading with version check, IndexedDB storage |
| `src/player/engine.ts` | Plays a dialog along a path of choice indices; `findPath` for full-text jumps. No UI code |
| `src/text/markup.ts` | The game's inline markup (`{n}`, `{g|…}`, `{mf|…|…}`, `{name}`, …) |
| `src/search/` | Index search, filters and full-text search |
| `src/state.ts` | App state: bundle lifecycle, route (`#/<dialogId>/<i>.<i>…`), display settings (locale, gender, name, comments) and theme, in localStorage, derived memos |
| `src/themes/` | Color themes: one CSS file each, registered in `themes.ts` |
| `src/ui/` | Components: `App` (shell, loader), `Sidebar` (search), `DialogPanel` (transcript, choices) |

## Player semantics

The explorer is not a simulator: conditions never hide or block, and wherever the game decides, the user chooses
(spec §5.3). A choice point with one option proceeds automatically. Decisions beyond the spec, from the data:

* Sequences keep a stack. A branch that ends returns to the innermost sequence; with none left, the dialog ends.
* A sequence entry with its own `continue`/`answers` offers "next in sequence" first, then its own flow.
* Page cues with conditions are all shown, labeled; they are not play/skip choices.
* Nodes with `once` count as conditional for fall-through.
* Option order is part of the URL format. Prefer appending new options over reordering existing ones.
* Display settings (gender, name, comments) only change rendering; keep them out of `src/player/`.

## Themes

Components are styled with Tailwind's palette for the dark theme (the default). Each other theme is a CSS file in
`src/themes/` that overrides the `--color-<hue>-<step>` variables under `[data-theme="<id>"]`, plus `color-scheme`;
import it in `index.css` and list it in `themes.ts`. The light theme mirrors the scales, so `neutral-950` is the page
background and `neutral-100` the strongest text in both. A component that starts using a new hue needs that hue added
to `light.css`, or it keeps its dark values there. `index.html` applies the stored theme before the first paint.

## Tests and data

Tests use small synthetic dialogs, never game data. Keep game text out of the repository, including fixtures and
screenshots.
