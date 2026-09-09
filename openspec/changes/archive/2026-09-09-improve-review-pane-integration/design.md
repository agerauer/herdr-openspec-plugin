## Context

See proposal.md — Why. `curses_main` sets up curses (colors, `mousemask(ALL_MOUSE_EVENTS | REPORT_MOUSE_POSITION)`, `keypad`) and never sets an escape delay, so ncurses uses its default `ESCDELAY`. The run loop uses `screen.timeout(250)` (a redraw poll, unrelated to the Escape lag). Mouse events are dispatched through `handle_mouse`; `mouse_wheel_direction` even folds `REPORT_MOUSE_POSITION` into its wheel-down mask, but no hover behavior uses motion. `scripts/open_sidebar.py::resize_sidebar` sets the initial split via the Herdr layout socket: `ratio = 0.70 if in_second is not False else 0.30` (the review pane is the right/second child, so 0.70 leaves it 30%). A spike (`herdr api snapshot`/`schema`, env, `config.toml`) confirmed Herdr exposes no theme palette to plugins — only a theme *name* — so #2 is out of scope.

## Goals / Non-Goals

**Goals:**
- Escape leaves the viewer as promptly as Left.
- The pane opens at ~50% width.
- The terminal's native selection/copy works on demand, reusing Herdr's mechanism.

**Non-Goals:**
- Matching Herdr's exact theme colors (no API to read them; already inherits the ANSI palette).
- An in-app text-selection/clipboard reimplementation.
- Changing the redraw poll or any navigation semantics beyond the mouse toggle.

## Decisions

### Decision: Shorten the escape delay instead of hand-parsing escape sequences

Call `curses.set_escdelay(25)` during `curses_main` setup. Escape is the lead byte of arrow/function-key sequences, so ncurses waits `ESCDELAY` after a lone Escape before delivering `27`; the default is long enough to feel laggy, while Left (`KEY_LEFT`) is a complete keysym and returns immediately. 25 ms is imperceptible yet still admits real sequences on a local terminal.

- **Why:** One call, no change to key handling. Alternatives — hand-rolling escape-sequence parsing, or reading keys in raw mode — are far more code and risk mis-handling function keys.

### Decision: A mouse-capture toggle rather than an in-app selection reimplementation

Add a `toggle_mouse` action bound to `m` and a footer hint. It flips a `self.mouse_enabled` flag and calls `curses.mousemask(<mask>)` when enabling and `curses.mousemask(0)` when disabling. With the mask cleared, the terminal stops routing mouse events to the pane, so Herdr's native select-and-autocopy works exactly as in other panes; re-enabling restores in-pane clicks and wheel. Also drop `REPORT_MOUSE_POSITION` from the mask (motion is unused and is the most disruptive to selection).

- **Why:** Terminal mouse mode is binary — any in-app mouse tracking blocks the terminal's drag-select — so the only way to get native copy back is to release the mouse. Reusing Herdr's mechanism is ~10 lines and consistent with every other pane. Mirroring selection in-app (drag tracking + coordinate→text mapping + a highlight overlay + an OSC-52/`pbcopy`/`xclip` clipboard path) is a fragile mini-feature that duplicates Herdr; rejected.
- **Trade-off:** While suspended, in-pane clicks and wheel are inactive (keyboard navigation still works). The footer hint makes the state discoverable.

### Decision: Half-width launcher default

In `resize_sidebar`, set the split ratio to `0.50` in both branches (was `0.70`/`0.30`) and update the docstring. This only sets the initial split through the layout socket; if the socket call fails the pane still opens and stays user-resizable.

## Risks / Trade-offs

- **Very fast key repeat / slow SSH links** could in theory clip an escape sequence at 25 ms → the plugin targets local macOS/Linux terminals where 25 ms is ample; raise it if a real terminal proves flaky.
- **Mouse-suspended state is modal** → mitigated by the always-visible footer hint reflecting the state; keyboard navigation remains fully functional while suspended.
- **Dropping motion reporting** could remove a future hover feature → none exists today; re-add the mask bit if one is introduced.

## Migration Plan

`sidebar.py`: add `set_escdelay(25)`; build the mouse mask without `REPORT_MOUSE_POSITION`; add `self.mouse_enabled` (default true), a `toggle_mouse` action + `m` key + `apply_mouse_mask()` helper, and a footer hint in both footers. `scripts/open_sidebar.py`: change the ratio and docstring. Update `tests/test_sidebar.py` and `README.md`. No persisted state; rollback is a straight revert.

## Open Questions

- The mouse-toggle key letter (`m`) and the exact footer label are minor presentation choices settled in implementation; they do not affect the specs or the task breakdown.
