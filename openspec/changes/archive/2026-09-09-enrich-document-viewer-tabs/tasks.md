## 1. Non-standard artifact discovery

- [x] 1.1 In `discover_project_changes`, scan the change folder's top level for `*.md`, exclude `proposal.md`/`design.md`/`tasks.md`, and append one `doc:<filename>` artifact per remaining file (title from the stem), inserted after Tasks and before the spec artifacts; verify a unit test that a change with a `research.md` yields a `doc:research.md` artifact ordered after `tasks` and before any `spec:`
- [x] 1.2 Order tabs core → non-standard (`doc:`) → specs in `viewer_tab_items`; verify a unit test that the tab item order for a change with a non-standard doc and a spec is Proposal, Design, Tasks, the doc, then the spec

## 2. Color-coded, wrapping tab bar

- [x] 2.1 Add a header layout helper that wraps the back affordance plus all tabs across multiple rows for a given width (no clipping); verify unit tests that all tabs are placed across rows and each carries a select target, and that a tab whose row is beyond the available height is omitted
- [x] 2.2 Classify each tab by artifact key (standard / non-standard / spec) and render non-selected tabs in a per-group color, keeping the selected tab's emphasis; verify a unit test that standard, `doc:`, and `spec:` tabs draw with three distinct colors and the selected tab is reversed
- [x] 2.3 Add a shared helper that computes the viewer header height from the wrapped tab-row count, used by both `viewer_dimensions` and `draw_viewer`; verify a unit test that the reported header height matches the number of drawn header rows

## 3. Viewer header and footer

- [x] 3.1 Render the change name as a heading on the row above the tab bar, styled distinctly from the tabs; verify a headless `draw_viewer` test that the name is drawn above the first tab row with a non-tab style
- [x] 3.2 Draw the wrapped, color-grouped tab rows beneath the name and the separator below them, and adjust the content offset and `viewer_dimensions` so scrolling, the `%` indicator, and paging stay correct with the taller header; verify existing viewer scroll tests pass and a test that content begins below the header
- [x] 3.3 Add the `p/d/t/s docs` hint to the viewer footer and change `e edit` to `e folder`; verify a headless test that the viewer footer lists the p/d/t/s hint and an `e folder` hint

## 4. Unified edit action

- [x] 4.1 Simplify `edit()` to always open `change.path` with `code` (report unavailability when `code` is absent; no file edit, no `vi`), and confirm `e` dispatches it from both the change list and the viewer; verify unit tests that edit from an open document launches `code` on the change folder and reports the message when `code` is absent

## 5. Tests and docs

- [x] 5.1 Update viewer header/tab layout, edit-action, and footer tests for the new header, wrapping, grouping, and folder edit; verify `python3 -m unittest discover -s tests` passes
- [x] 5.2 Update `README.md` for non-standard artifact tabs, the three color groups, the multi-row tab bar, the change-name heading, and the unified `e` folder behavior; verify the README no longer says `e` edits the open file
