## Context

The sidebar currently computes list positions directly inside `draw_main`, caps change rows with `min(5, height // 4)`, and renders footer hints as one inert string. Input handling has no mouse setup or hit map. A single `move` method handles list navigation and document navigation; in viewer mode it multiplies every movement by the viewport height, which makes both arrow keys and page keys page-sized.

This change spans layout, rendering, input dispatch, and tests within the single dependency-free curses application. See `proposal.md` for motivation and `specs/sidebar-navigation/spec.md` for observable behavior.

## Goals / Non-Goals

**Goals:**

- Derive a stable main-view layout from the current pane dimensions and selected change.
- Make rendered rows and footer actions addressable through explicit mouse hit targets.
- Route keyboard and mouse activation through the same semantic actions.
- Separate line scrolling from page scrolling in the document viewer.
- Keep the implementation dependency-free and testable without a live terminal.

**Non-Goals:**

- Mouse hover, drag selection, context menus, or double-click behavior.
- Horizontal document scrolling or changes to Markdown wrapping.
- Changes to OpenSpec discovery, validation, task counting, or Herdr pane placement.
- Persisting navigation, scroll, or mouse state between sidebar processes.

## Decisions

### Centralize adaptive main-view layout

Introduce a pure layout calculation that determines the change-row window, artifact-row window, and reserved fixed regions from pane height. It will cap visible changes at 15, reserve space for the header, selected-change status and goal, message/footer rows, and a useful artifact area, then reduce change capacity when the full allocation does not fit. On extremely short panes, it will degrade to at least one change row and one artifact row when both collections are present rather than allowing regions to overlap.

The existing selection-centered windowing remains, but consumes the calculated capacity instead of a hard-coded five-row cap. A pure calculation is preferred over accumulating row arithmetic during drawing because boundary cases and resize behavior can be unit-tested directly.

Alternative considered: change the cap from 5 to 15 without height-aware allocation. This would meet the tall-pane case but could push artifacts and footer content off short panes.

### Build mouse hit targets from rendered geometry

Each draw will clear and rebuild a list of rectangular hit targets for the exact change rows, artifact rows, and footer segments that were rendered. Targets will carry a semantic action plus any change/artifact index required for dispatch. Mouse clicks will resolve against this list instead of duplicating layout arithmetic in the input handler.

Alternative considered: recompute row positions in the mouse handler. That duplicates height-dependent layout rules and risks clicks targeting stale or different rows after resize.

### Share semantic actions across keyboard and mouse input

Refactor open, back, validate, edit, and close behavior into small action methods or a common dispatcher. Keyboard branches and footer hit targets will invoke the same operations. A change-row click selects and focuses that change; an artifact-row click selects it and invokes the same open-or-missing behavior as Enter.

Alternative considered: synthesize keyboard codes from mouse clicks. Direct semantic dispatch is clearer, avoids curses key-code coupling, and makes hit-testing behavior easier to test.

### Treat one mouse-wheel event as one visual line

Enable curses mouse reporting and map upward/downward wheel events to a dedicated line-scroll operation. Up/Down use the same line-scroll operation in viewer mode. Page Up/Page Down use a separate page-scroll operation based on the visible document height. Final clamping remains tied to the wrapped-line count calculated for the current width.

Alternative considered: keep one movement method with a multiplier flag. Separate operations make the input contract explicit and avoid reintroducing the current accidental coupling.

### Register only visible footer segments

Render footer actions as individually measured segments and create a hit target only for the portion that fits. This keeps click behavior aligned with what the user can see in narrow panes.

Alternative considered: assign fixed column ranges for all actions. Fixed ranges would make clipped or invisible labels clickable.

## Risks / Trade-offs

- [Terminal mouse protocols vary in how wheel activity is reported] → use curses mouse constants, treat each delivered event consistently, and retain complete keyboard navigation.
- [Dynamic content and resize can invalidate coordinates] → rebuild the layout and hit-target list on every draw before reading the next input event.
- [Reserving artifact space reduces change rows on short panes] → prioritize a usable complete sidebar and expose the full 15-row capacity whenever height permits.
- [Footer labels may not all fit at very small widths] → register clicks only for visible segments and preserve keyboard shortcuts for every action.

## Migration Plan

No data migration is required. The updated sidebar process takes effect after reopening the linked plugin pane; rollback is the corresponding source revert and pane restart.
