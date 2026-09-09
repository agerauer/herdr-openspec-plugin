## Why

Three rough edges in how the review pane sits inside Herdr: leaving a document with Escape lags noticeably (arrow-left is instant), the pane opens at only ~30% width where 50% reads better, and the pane's mouse capture blocks Herdr's native select-and-autocopy that works in every other pane — so you can't copy text out of a document.

## What Changes

- Eliminate the Escape latency when leaving the document viewer by shortening the terminal's escape-sequence disambiguation delay. Escape becomes as responsive as arrow-left. (Root cause: Escape is the lead byte of every arrow/function-key sequence, so ncurses waits `ESCDELAY` — often ~1s — before delivering a lone Escape.)
- Open the review pane at about half the available width instead of ~30%. (Launcher default in `scripts/open_sidebar.py`; manual resizing still works.)
- Add a key that toggles the pane's mouse handling off and on. With it off, the terminal's own text selection works, so Herdr's mark-and-autocopy behaves exactly as in bash/agent panes; with it on, in-pane clicks and wheel scrolling work as before. Advertise the toggle in the footer. Also stop requesting mouse-motion reporting, which is unused and the most disruptive to selection.

## Capabilities

### New Capabilities
<!-- None. These extend the existing review-pane interaction behavior. -->

### Modified Capabilities
- `sidebar-navigation`: adds a responsive-Escape guarantee for leaving the document viewer, a mouse-capture toggle that frees the terminal's native selection/copy (advertised in the footer), and a half-width default when the pane first opens.

## Impact

- **Code**: `sidebar.py` — set a short escape delay during curses setup; add a mouse-toggle action + key (`m`) and footer hint that calls `curses.mousemask` on/off and tracks the state; drop `REPORT_MOUSE_POSITION` from the mouse mask. `scripts/open_sidebar.py` — `resize_sidebar` split ratio `0.70/0.30 → 0.50` (and its docstring).
- **Tests**: `tests/test_sidebar.py` — add tests for the mouse-toggle action/state and its footer hint; adjust any footer/mouse expectations.
- **Docs**: `README.md` — note the 50% default width and the mouse-toggle key in Controls.
- **Out of scope**: matching Herdr's exact theme palette — a spike found Herdr exposes no theme colors to plugins (config only names the theme; nothing in `herdr api snapshot`/`schema`/env), and the pane already inherits the theme's ANSI palette and background via `use_default_colors()`; deeper matching would need a new Herdr API. Also out of scope: an in-app selection/copy reimplementation (reuses Herdr's native mechanism instead).
