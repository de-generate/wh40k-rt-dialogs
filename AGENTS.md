# Notes for agents

This repository holds two projects about the dialogs of *Warhammer 40,000: Rogue Trader*:

* `wh40k-rt-dialog-extractor/`: standalone Python tool (raw game export → `dialogs.json` → output formats).
  Read its `AGENTS.md` before working on it.
* `wh40k-rt-dialog-explorer/`: web app for browsing dialogs, in planning. It consumes the extractor's output.

Keep the extractor independent of the explorer: the dependency points one way only (explorer → extractor).

Game data (`data/`, `dialogs.json`, generated scripts) is copyrighted and ignored by git. Prefer keeping it out of
commits, tests and fixtures; tests use a synthetic export instead.
