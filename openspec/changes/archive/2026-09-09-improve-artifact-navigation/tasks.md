## 1. Artifact ordering and layout

- [x] 1.1 Reorder discovery to build Proposal, Design, Tasks, and then deterministically sorted Specs (including the no-spec placeholder), add core-artifact key lookup, and verify discovery tests cover multiple specs and missing core files.
- [x] 1.2 Extend main-view layout to allocate surplus pane height beyond the four-artifact baseline while preserving the 15-change target and selected-artifact visibility, and verify layout tests cover tall, constrained, and minimum-height panes.
- [x] 1.3 Render the full navigable artifact count as `ARTIFACTS (N)` and verify drawing tests cover existing and missing artifact rows without changing row hit targets.

## 2. Navigation actions

- [x] 2.1 Register the viewer header back label as a clipped mouse target routed through the shared back action, and verify click tests cover the target boundary and clicks elsewhere in the header.
- [x] 2.2 Make Escape explicitly return main-view artifact focus to the selected change while retaining the current viewer-back selection, and verify state-transition tests cover Enter then Escape, repeated Escape, and returning from a document.
- [x] 2.3 Add change-list-only `p`, `d`, and `t` actions that select and open Proposal, Design, and Tasks by artifact key, and verify tests cover existing targets, missing targets, and ignored shortcuts outside change-list focus.

## 3. Viewer input and editing

- [x] 3.1 Add a pure mouse-wheel direction normalizer for exposed curses constants and the ncurses button-5 fallback, route each recognized event to one signed line scroll, and verify independent tests for upward, downward, boundary, and unrecognized states.
- [x] 3.2 Replace `$EDITOR` selection with PATH-based `code` detection and a `vi` fallback using argv execution, and verify mocked launch tests cover both editor branches, the selected artifact path, curses restoration, and reload.

## 4. Documentation and integration verification

- [x] 4.1 Update the README controls and feature description for artifact ordering/count/capacity, header back clicks, direct shortcuts, bidirectional wheel scrolling, and VS Code/vi behavior, and verify the documentation matches the implemented bindings and fallback order.
- [x] 4.2 Run `python3 -m unittest discover -s tests -v`, validate `improve-artifact-navigation`, and perform a live Herdr smoke test with at least five artifacts to verify ordering, count, adaptive height, Enter/Escape focus, top-back clicks, both wheel directions, direct shortcuts, and editor launch.
