## Why

The document viewer's tab bar only knows the three standard artifacts (Proposal, Design, Tasks) and specifications; any other document a change keeps in its folder is invisible, so reviewers cannot open it. The tabs also read as one undifferentiated row — nothing distinguishes a spec from a core artifact — the change name sits below the tabs styled like them, and the viewer never advertises the `p`/`d`/`t`/`s` shortcuts. Finally, `e` behaves differently in the viewer (edits the open file) than in the change list (opens the folder), which is inconsistent.

## What Changes

- Discover **non-standard artifacts** — any `.md` file directly in a change's folder other than `proposal.md`, `design.md`, and `tasks.md` — and show them as tabs in the document viewer, positioned after Tasks and before the specifications.
- **Color-code the tab bar into three groups**: the standard artifacts (Proposal, Design, Tasks), the non-standard artifacts, and the specifications each get a distinct color, so a tab's kind is visible at a glance. The selected tab keeps its selected emphasis.
- Make the tab bar **wrap onto multiple rows** when the tabs do not fit the pane width, instead of clipping the overflow, so every tab stays reachable in a narrow pane.
- Move the **change name above the tab bar** and give it a style distinct from the tabs (not a dim row beneath them), so it reads as the document's heading rather than another tab.
- **Advertise the `p`/`d`/`t`/`s` document shortcuts** in the document viewer's footer alongside back, edit, and close.
- **BREAKING**: Make `e` open the whole change folder in VS Code from the document viewer too, matching the change list. The previous behavior of editing just the open document with `code`/`vi` is removed; open a specific file from within the editor once the folder is open.

## Capabilities

### New Capabilities
<!-- None. This extends the existing document viewer and edit behavior. -->

### Modified Capabilities
- `document-viewer-tabs`: The tab bar gains non-standard-artifact tabs (after Tasks, before specs), three color-coded artifact groups, multi-row wrapping when tabs overflow, and the change name shown as a distinctly styled heading above the tabs.
- `sidebar-navigation`: The edit action opens the change folder from the document viewer as well as the change list (single-file edit removed), and the document viewer's footer advertises the `p`/`d`/`t`/`s` shortcuts.

## Impact

- **Code**: `sidebar.py` — `discover_project_changes` gains non-standard `.md` discovery (new `doc:` artifacts); `viewer_tab_items` orders core → non-standard → specs; a new wrapping header layout replaces the single-row `viewer_header_segments`; `draw_viewer` renders the name heading above a color-coded, multi-row tab bar and a footer that lists `p`/`d`/`t`/`s`; the viewer's `e` branch and `edit()` open the change folder; the content offset math adapts to the variable header height.
- **Tests**: `tests/test_sidebar.py` — update viewer header/tab layout, edit-action, and footer tests; add tests for non-standard discovery, tab grouping/color, wrapping, and the name heading.
- **Docs**: `README.md` — describe non-standard artifact tabs, the color groups, the multi-row tab bar, and the unified `e` folder behavior.
- **Out of scope**: non-Markdown files as artifacts; a dedicated keyboard shortcut for non-standard artifacts (reachable via tab click and Left/Right tab navigation); the change-list card layout.
