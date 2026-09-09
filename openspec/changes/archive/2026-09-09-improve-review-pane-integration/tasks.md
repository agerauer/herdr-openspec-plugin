## 1. Responsive Escape

- [x] 1.1 Call `curses.set_escdelay(25)` during `curses_main` setup so a lone Escape is delivered promptly; verify by manual run that Escape leaves the document viewer without the previous lag (and that arrow-key navigation still works)

## 2. Mouse-capture toggle

- [x] 2.1 Build the mouse mask without `REPORT_MOUSE_POSITION`, and remove it from `mouse_wheel_direction`'s wheel-down mask; verify wheel scrolling in the viewer still works and a unit test that motion bits are no longer part of the wheel mask
- [x] 2.2 Add `self.mouse_enabled` (default true) and an `apply_mouse_mask()` helper that calls `curses.mousemask(<mask>)` when enabled and `curses.mousemask(0)` when disabled; verify a unit test that toggling the flag drives the two mask values
- [x] 2.3 Add a `toggle_mouse` action bound to `m` (in both main and viewer contexts) that flips the flag, re-applies the mask, and shows a status message; verify a unit test that `handle(ord("m"))` dispatches `toggle_mouse` and flips `mouse_enabled`
- [x] 2.4 Add a mouse-toggle hint to the main and viewer footers reflecting the current state (e.g. `m mouse`); verify a headless draw test that the hint appears in both footers

## 3. Half-width default

- [x] 3.1 In `scripts/open_sidebar.py::resize_sidebar`, set the split ratio to `0.50` in both branches and update the docstring/comment; verify by manual run that a freshly opened review pane takes about half the width and can still be resized

## 4. Tests and docs

- [x] 4.1 Run the suite and adjust any footer/mouse expectations for the new hint and mask; verify `python3 -m unittest discover -s tests` passes
- [x] 4.2 Update `README.md` — 50% default width and the `m` mouse-toggle key in Controls; verify the Controls table lists the mouse toggle
