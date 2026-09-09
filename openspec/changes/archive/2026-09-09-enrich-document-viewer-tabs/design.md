## Context

See proposal.md — Why. Today `discover_project_changes` builds a change's artifacts from exactly `proposal.md`, `design.md`, `tasks.md`, and `specs/**/*.md` (or a `specs` placeholder); nothing else in the folder is modeled. `viewer_tab_items` emits core tabs (from `VIEWER_CORE_TABS`) then specs. `viewer_header_segments` lays the back affordance and tabs on a single row and scrolls/clips to keep the selected tab visible. `draw_viewer` draws that tab row (row 0), the change name dim on row 1, a separator on row 2, then content from row 3, with `visible = height - 5`. The viewer's `e` edits the open file (`code`/`vi`); the change list's `e` opens the folder (from the just-shipped `redesign-change-list-cards`).

## Goals / Non-Goals

**Goals:**
- Surface every `.md` a change keeps in its folder, and make each tab's kind readable by color.
- A tab bar that wraps instead of clipping, and a change name that reads as a heading above it.
- One consistent `e` (open the change folder) across the change list and the viewer.
- Keep the viewer's scroll geometry correct as the header height varies.

**Non-Goals:**
- Non-Markdown files as artifacts; a dedicated shortcut key for non-standard artifacts (reachable via click and Left/Right).
- The change-list card layout, and the document Markdown renderer.

## Decisions

### Decision: Non-standard artifacts are root-level `.md` files, modeled as `doc:` artifacts

`discover_project_changes` scans the change folder's top level (non-recursive) for `*.md`, excludes `proposal.md`/`design.md`/`tasks.md`, and appends one `Artifact` per remaining file with key `doc:<filename>` and a title derived from the file stem. These are inserted after Tasks and before the spec artifacts. Specs are unaffected because they live under `specs/` and are not matched by a top-level glob.

- **Why:** Matches the user's definition ("other `.md` in the change root") and reuses the existing `Artifact`/content-reading machinery, so non-standard documents render in the viewer exactly like the standard ones.
- **Alternatives:** Any file regardless of extension — rejected (non-Markdown won't render usefully); schema-declared artifacts — rejected (the sidebar has no schema-artifact parsing and it is far larger).

### Decision: Tab groups are classified by artifact key and colored

`viewer_tab_items` orders tabs core → `doc:` → specs. In `draw_viewer`, each non-selected tab's color is chosen by its artifact key: standard (`proposal`/`design`/`tasks`) in one color, non-standard (`doc:`) in a second, specifications (`spec:` / `specs`) in a third; the selected tab keeps `A_REVERSE | A_BOLD`. Concrete pairs (e.g. standard = cyan, non-standard = yellow, specs = green) are a presentation detail settled in code.

- **Why:** The group is derivable from the key already threaded through segments (`segment.index` → artifact), so no new data needs to flow through the layout.

### Decision: Wrapping header with the change name as a heading

A new layout helper wraps the back affordance plus all tabs across as many rows as the width needs (like `wrap_footer_segments`), so every tab is shown and the keep-selected-visible scroll logic is no longer needed. `draw_viewer` renders: row 0 the change name (bold + accent, distinct from tabs); the wrapped tab rows beneath it; then a separator; then content. A shared helper computes the header height from the wrapped tab-row count so `viewer_dimensions` (scroll math) and `draw_viewer` (rendering) agree, keeping `clamp_document_offset`, the `%` indicator, and paging correct as the header grows.

- **Why:** Wrapping makes all tabs reachable in a narrow pane and removes the scroll/clip complexity; a single header-height helper prevents the scroll offset and the render from drifting apart.

### Decision: `e` opens the change folder everywhere

`edit()` always opens `change.path` with `code` (reporting unavailability when `code` is absent); the viewer's file-edit branch and the `vi` fallback are removed. `handle` already dispatches `edit` for `e` in both contexts. The viewer footer's hint changes from `e edit` to `e folder` and gains a `p/d/t/s docs` legend; the footer already wraps.

- **Why:** One behavior for `e` (the user's consistency request). A folder is not a file, so `vi` was never a sensible fallback.

## Risks / Trade-offs

- **Header height now varies with width** (wrapped tab rows) → a single header-height helper feeds both the scroll math and the renderer; a test pins that they agree.
- **`e` no longer edits a single file** (BREAKING) → accepted per the user; a specific file is still editable once the folder is open in VS Code.
- **A stray root `.md`** (e.g. a `README.md` in a change folder) becomes a tab → intended: any non-standard document is meant to be reachable.
- **Very short panes** may not fit all wrapped tab rows → undrawn tabs get no click target (as the removed clip requirement guaranteed for the horizontal case).

## Migration Plan

Add non-standard discovery to `discover_project_changes`; order them in `viewer_tab_items`; add the wrapping header helper and header-height helper; rewrite `draw_viewer`'s header (name heading + wrapped, color-grouped tabs) and its content-offset math and `viewer_dimensions`; simplify `edit()` to the folder path and update the viewer footer. Update viewer header/tab/edit/footer tests and add discovery, grouping, wrapping, and heading tests. Update `README.md`. No persisted state changes; rollback is a straight revert.

## Open Questions

- The exact colors for the three tab groups and the change-name heading are presentation details settled in code; they do not affect the specs, the approach, or the task breakdown.
