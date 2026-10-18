# Rogue Trader dialog explorer

Web app for searching the dialogs of *Warhammer 40,000: Rogue Trader* and clicking through them like in the game.

A pure static site: users load their own export, a bundle produced by the extractor
(`python -m rt_dialogs output explorer-bundle`, spec in `../wh40k-rt-dialog-extractor/EXPLORER_BUNDLE.md`), so no
game data is hosted. The bundle stays in the browser (IndexedDB); nothing is uploaded.

## Use

```
pnpm install
pnpm dev     # development server
pnpm build   # static site in dist/, deployable to any static host
pnpm test    # unit tests
```

* **Left:** search dialogs by name, tag, path or speaker, or switch to full-text search in the current locale.
  Filters for source, type and chapter. Deleted dialogs and dialogs without nodes are never listed.
* **Right:** the dialog played so far and the current choice. Every option is shown and clickable; conditions are
  only labels. Wherever the game decides on its own (alternatives, checks, conditional sequence entries), you
  choose. Keys: `1`–`9` pick an option, `Backspace` goes back.
* Display settings next to the locale: player gender (picks the `{mf|…}` variant) and name (fills `{name}`); unset,
  both variants and the placeholder are shown. Designer comments are hidden unless enabled. The settings are
  remembered in the browser and never change the dialog flow.
* The theme picker in the top bar switches between the dark and light themes; the choice is remembered too.
* The path lives in the URL, so reloads and shared links keep it. A full-text hit opens the dialog at the shortest
  path that shows the text.
