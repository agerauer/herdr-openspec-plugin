## Why

Several navigation paths in the review sidebar are inconsistent or incomplete: important artifacts are buried behind specs, the artifact viewport wastes available height, some back and scroll interactions do not work reliably, and opening a document for editing does not prefer the user's graphical editor. These issues make reviewing a change slower and force unnecessary keyboard or terminal workarounds.

## What Changes

- Make the document viewer's top back affordance clickable and ensure Escape returns focus from the artifact list to the change list after Enter moved it there.
- Order artifacts as Proposal, Design, Tasks, followed by every spec in deterministic path order.
- Show the total artifact count in the `ARTIFACTS` heading and expand the artifact viewport beyond four rows whenever pane height permits, while keeping the selected artifact visible.
- Normalize mouse-wheel handling so both upward and downward document scrolling work reliably by one wrapped visual line per wheel step.
- Add `p`, `d`, and `t` shortcuts in the main view to open Proposal, Design, and Tasks directly for the selected change, with the normal missing-artifact feedback when a target does not exist.
- Make the viewer's edit action open the current document with the `code` command when it is available on `PATH`, falling back to `vi` otherwise.
- Update help text and automated coverage for the expanded keyboard and mouse behavior.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `sidebar-navigation`: Extend artifact ordering and capacity, back/focus behavior, document-wheel reliability, direct artifact shortcuts, and editor selection.

## Impact

- `sidebar.py`: artifact discovery order, adaptive layout, header rendering, hit targets, focus transitions, mouse-event normalization, direct-open actions, and editor command selection.
- `tests/test_sidebar.py`: regression and behavior coverage for ordering, layout capacity/counts, top-back clicks, Escape focus, bidirectional wheel scrolling, direct shortcuts, and editor fallback.
- `README.md`: controls and editor behavior documentation.
- Runtime dependencies remain unchanged; VS Code integration is optional and detected through the `code` executable on `PATH`.
