## Why

The main view splits each change's information across two places: a compact one-line row in the change list (`›◆ name … X/Y`) and a separate detail panel below it (status, description, a navigable ARTIFACTS list) that only reflects the currently selected change. A reviewer scanning several changes cannot see any change's status or description without selecting it, and the layout spends vertical space on a per-change artifact list that duplicates the document viewer's own tabs.

## What Changes

- Render each change as an inline multi-line **card** in the change list instead of a one-line row plus a separate detail panel:
  - Line 1: a selection marker and the **bold** change name
  - Line 2: `STATUS · N Artifacts · done/total` (status color-coded)
  - Line 3: the change's description
  - a blank line separates cards
- Show the full card for **every** change, not only the selected one, so status, artifact count, task progress, and description are visible while scanning.
- **BREAKING**: Remove the main view's always-visible ARTIFACTS list and its focus mode. Artifacts are opened with the existing `p`/`d`/`t`/`s` shortcuts and with Enter (which opens the Proposal), and are browsed via the document viewer's tabs (see `document-viewer-tabs`). The `X/Y` task progress and artifact count move into the card's status line.
- Drop the `◆` worktree-touched glyph. Touched changes stay grouped at the top and are indicated by **color** on the change name; the icon is redundant.
- Extend the edit action: pressing `e` while the change list is focused SHALL open the selected change's whole folder in `code`. Pressing `e` while a document is open continues to edit that document. When `code` is not on `PATH`, opening a folder is reported as unavailable rather than falling back to `vi`.

## Capabilities

### New Capabilities
<!-- None. This changes how existing change-list and edit behavior work; the requirements live in the capabilities below. -->

### Modified Capabilities
- `sidebar-navigation`: Change rows become multi-line cards shown for every change; the main-view artifact list, its capacity rules, its focus-return behavior, and its mouse rows are removed (artifacts move to the viewer tabs); Enter opens the Proposal; the edit action gains a change-folder mode; the worktree marker becomes color rather than a glyph.
- `change-list-task-progress`: Task progress `X/Y` is displayed on the card's status line rather than as a right-aligned column in a single-line row, and remains legible without colliding with the change name.

## Impact

- **Code**: `sidebar.py` — `format_change_row` is replaced by a card renderer; `calculate_main_layout` drops the status/goal/artifact-header/artifact-window regions and windows the list by card height; `draw_main` renders cards and their hit targets; the artifact-list focus state and its key/mouse handling are removed; the `e` handler branches on context (change folder vs. open document); the worktree marker rendering changes from glyph to color.
- **Tests**: `tests/test_sidebar.py` — layout, `format_change_row`, artifact-list navigation, focus-return, and worktree-marker tests are updated or removed; new tests cover card rendering, per-change cards, the folder-edit action, and color-coded touched changes.
- **Docs**: `README.md` — update the "What it shows" and "Controls" sections for the card list, the removed artifact list, and the `e` folder action.
- **Out of scope**: the document viewer and its Markdown rendering and tabs; change discovery, sorting, and worktree prioritization logic (only the touched *marker* presentation changes).
