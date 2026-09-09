## Why

The sidebar currently limits the change list to five rows, exposes navigation only through the keyboard, and scrolls documents by a full viewport for ordinary arrow input. These constraints make larger change sets harder to scan and precise document reading unnecessarily cumbersome.

## What Changes

- Increase the visible change-list capacity to as many as 15 changes when the pane height permits.
- Calculate the actual change-list capacity from the current pane height so the selected-change details, artifact list, messages, and footer remain usable without overlap.
- Make visible change rows and artifact rows mouse-clickable.
- Make the action hints displayed in the bottom footer mouse-clickable, with the same behavior as their keyboard equivalents.
- Scroll an open document by one visual line for each Up/Down keypress or mouse-wheel step while retaining page-sized movement for Page Up/Page Down.
- Add layout, mouse hit-testing, and scroll-distance coverage.

## Capabilities

### New Capabilities

- `sidebar-navigation`: Defines adaptive list capacity and consistent keyboard and mouse navigation across the change list, artifact list, document viewer, and footer actions.

### Modified Capabilities

None.

## Impact

- `sidebar.py`: adaptive layout calculation, mouse initialization and hit targets, click dispatch, and separate line/page scrolling behavior.
- `tests/test_sidebar.py`: layout capacity, hit-testing, and document-scroll regression coverage.
- `README.md`: mouse controls, revised document scrolling, and the expanded change-list capacity.
- No changes to OpenSpec formats, Herdr APIs, plugin state, or external dependencies.
