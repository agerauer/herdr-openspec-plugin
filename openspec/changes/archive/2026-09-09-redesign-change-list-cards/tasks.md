## 1. Card rendering

- [x] 1.1 Add a card renderer (replacing `format_change_row`) that produces a change's three lines — selection marker + bold name, `STATUS · N Artifacts · done/total`, and a truncated description — plus the status/artifact/progress segments; verify a unit test that a READY change with 4 artifacts and 0/16 tasks yields a status line reading `READY · 4 Artifacts · 0/16`
- [x] 1.2 Reserve the `X/Y` value on the status line and shorten the status/artifact text first when the line is too narrow; verify a unit test that a constrained width keeps the complete `X/Y` while trimming other status-line content
- [x] 1.3 Render worktree-touched change names in the accent color and drop the `◆` glyph; verify a unit test that a touched change's name carries the touched color and no row contains `◆`

## 2. Layout and windowing

- [x] 2.1 Rewrite `calculate_main_layout` to remove the status, goal, artifact-header, and artifact-window regions and fit as many whole fixed-height cards as the height allows (`available_height // CARD_ROWS`, no fixed cap); verify unit tests for the number of visible cards at a tall and a short pane height and that more than 15 cards show in a very tall pane
- [x] 2.2 Window the card list around the selection so the selected card stays visible when not all cards fit; verify a unit test that selecting a change below the visible window scrolls it into view

## 3. Draw and interaction

- [x] 3.1 Update `draw_main` to draw every change as a card with per-card mouse hit targets and the selected card emphasized; verify a headless draw over the mock screen emits the three card lines per visible change and a hit target covering each card
- [x] 3.2 Left-click on any card line selects that change and focuses the change list; clicking empty space leaves selection unchanged; verify unit tests for a click on a card and a click on empty space
- [x] 3.3 Open the selected change's Proposal on Enter (or report it missing); verify a unit test that Enter with an existing Proposal opens it in the viewer
- [x] 3.4 List all main-view shortcuts in the footer (move, open, p/d/t/s docs, edit, validate, refresh, close), wrapping onto further rows when the pane is narrow; the open, docs (opens Proposal), edit, validate, refresh, and close hints are clickable, and movement is a display-only legend; verify a unit test that the footer includes the refresh hint, that the docs hint dispatches open, and that the movement legend registers no click target

## 4. Remove the artifact list

- [x] 4.1 Delete the `"artifacts"` focus state, Tab toggling, the artifact window/heading, and the artifact-row key and mouse handling from `handle`/`draw_main`; verify the suite has no remaining references to artifact-list focus and `python3 -m unittest discover -s tests` passes
- [x] 4.2 Confirm `p`/`d`/`t`/`s` still open artifacts from the change list and the viewer with the artifact list gone; verify existing shortcut tests pass (updated for the removed focus state)

## 5. Edit action

- [x] 5.1 Branch the `e` handler: with a document open keep `code`/`vi` on the artifact; with the change list focused open the selected change's folder with `code`, reporting unavailability when `code` is absent (no `vi` fallback); verify unit tests for the folder-open path and the missing-`code` message

## 6. Tests and docs

- [x] 6.1 Update or remove tests tied to the old layout (`format_change_row`, artifact-list capacity/navigation, focus-return, worktree glyph) and add the card tests above; verify `python3 -m unittest discover -s tests` passes
- [x] 6.2 Update `README.md` "What it shows" and "Controls" for the card list, the removed artifact list, and the `e` change-folder action; verify the README no longer describes the `◆` marker or a separate artifact list
