## Context

See proposal.md — Why. Today `draw_main` renders two things: a compact change list where `format_change_row` prints one fixed-width line per change (`›◆ name … X/Y`), and, below it, a detail panel for the *selected* change built by `calculate_main_layout` — a status row, up to two goal (description) rows, and a navigable `ARTIFACTS (N)` list with its own focus mode (`self.focus in {"changes", "artifacts"}`), Tab toggling, Enter-to-artifacts, and per-artifact mouse rows. `calculate_main_layout` allocates all of these regions from pane height. The document viewer already provides tab-based artifact navigation (`document-viewer-tabs`), which the user relies on.

## Goals / Non-Goals

**Goals:**
- One self-contained multi-line card per change, shown for every change, carrying everything the old row + detail panel showed except the artifact list.
- Remove the main-view artifact list and its focus mode; keep artifact opening via `p`/`d`/`t`/`s` and Enter, and browsing via the viewer tabs.
- Predictable vertical layout and selection windowing with taller cards.
- Preserve mouse selection and footer behavior.

**Non-Goals:**
- The document viewer, its Markdown rendering, or its tabs.
- Change discovery, sorting, or worktree-prioritization logic — only the *presentation* of the touched marker changes.
- Wrapping the card description across multiple lines (kept to one truncated line for fixed card height).

## Decisions

### Decision: Fixed-height cards windowed by card, replacing the row + detail panel

Each change renders as a fixed 3-line card — name line, status line, description line — with one blank spacer line between cards. `format_change_row` is replaced by a card renderer that returns the three lines (or draws them directly). `calculate_main_layout` loses the status/goal/artifact-header/artifact-window regions and instead fits whole cards: `visible_cards = available_height // CARD_ROWS` with no fixed upper limit, with a card-based centered window around the selection so the selected card stays visible.

- **Why:** A fixed card height keeps windowing and click hit-testing simple (row → card index is integer division) and matches the mockup, which shows one description line per change. Variable-height cards (wrapped descriptions) would complicate the window math for little gain in a narrow pane.
- **Alternatives:** Accordion (only the selected change expands) — rejected: the user chose "every change shows a full card." Wrapped multi-line descriptions — rejected for fixed-height simplicity; the description is truncated with an ellipsis instead.

### Decision: Remove the artifact-list focus mode; Enter opens the Proposal

Delete the `"artifacts"` focus state, Tab toggling, the artifact window, and the `ARTIFACTS (N)` heading. The main view has a single focus (the change list). Enter on the selected change opens its Proposal in the viewer (or reports it missing); `p`/`d`/`t`/`s` continue to open specific artifacts; the viewer's tabs handle switching among them.

- **Why:** The artifact list duplicated the viewer tabs the user already uses. Removing it simplifies `handle`, `draw_main`, and the layout, and frees the vertical space the cards need.
- **Alternatives:** Keep the artifact list below the cards — rejected by the user's steer (artifacts live in the viewer tabs). Inline artifact rows under the selected card — rejected: reintroduces a focus mode and variable card height.

### Decision: Touched changes shown by name color, not a glyph

Drop the `◆` marker. Render a worktree-touched change's name in an accent color (the existing cyan "important" pair) while untouched names use the default color. Touched changes stay grouped at the top (unchanged sort).

- **Why:** The icon and the color would be redundant; the user asked to drop the icon and keep color. Reusing the existing accent pair avoids introducing new color semantics.

### Decision: Context-sensitive edit action

`e` branches on context: with a document open, it keeps today's behavior (`code` the artifact, else `vi`). With the change list focused and no document open, it opens the selected change's folder with `code`, and reports "opening the folder is unavailable" when `code` is absent — no `vi` fallback, since `vi` cannot usefully open a directory.

- **Why:** A folder is not a file; `vi <dir>` is not a sensible editor invocation. Reporting unavailability is clearer than a broken fallback.

### Decision: The footer lists all main-view shortcuts

The change-list footer enumerates the full shortcut set (move, open, the `p`/`d`/`t`/`s` document keys, edit, validate, refresh, close) rather than a subset, wrapping onto further rows (`wrap_footer_segments`) when the pane is too narrow for one row so nothing is dropped; the layout reserves the wrapped rows. The open, document-keys, edit, validate, refresh, and close hints are clickable — the document-keys hint dispatches `open` (the selected change's Proposal, matching the `p` key). Only the movement hint is a display-only legend (an empty action), so `draw_footer` skips a click target for it.

- **Why:** Discoverability — the shortcuts should be visible without consulting the README, and in a narrow pane that means wrapping rather than clipping. Movement stays a legend because a single click cannot express a direction.

## Risks / Trade-offs

- **Fewer changes visible at once** (cards are ~4× taller than rows) → accepted per the user's "every change shows a full card" choice; the list fills the pane with as many whole cards as fit (no fixed cap) and windows around the selection.
- **Removing the artifact list changes muscle memory and breaks its tests** → the ADDED/REMOVED spec deltas make the new model explicit; `p`/`d`/`t`/`s`, Enter, and the viewer tabs preserve every open path; affected tests are rewritten with the layout change.
- **Fixed one-line description truncates long descriptions** → acceptable for scanning; the full text is visible once the Proposal is open. Truncation length is a presentation detail.
- **Status line overflow in narrow panes** → reserve the `X/Y` value and shorten the status/artifact text first (see change-list-task-progress delta) so progress stays legible.

## Migration Plan

Replace `format_change_row` with the card renderer and rewrite `calculate_main_layout`/`draw_main` for card windowing; delete the artifact-list focus state and its key/mouse handling; branch the `e` handler; change the touched marker from glyph to color. Update `tests/test_sidebar.py` (layout, row formatting, artifact-list navigation, focus-return, worktree-marker) and add card tests. Update `README.md`. No persisted state or external contract changes, so rollback is a straight revert.

## Open Questions

- Exact colors for the status line and the touched-change name, the selection marker glyph, and the description truncation length are presentation details to settle in implementation; they do not affect the specs, the approach, or the task breakdown.
