## 1. Confirm the code satisfies the corrected requirement

- [x] 1.1 Verify `MOUSE_MASK` in `sidebar.py` includes `REPORT_MOUSE_POSITION`, so the event type is actually requested and `getmouse()` can decode a downward step. Verify: `python3 -c "import curses, sidebar; assert sidebar.MOUSE_MASK & curses.REPORT_MOUSE_POSITION"`.
- [x] 1.2 Verify `mouse_wheel_direction` maps the motion bit to `1` (down) and `BUTTON4_PRESSED` to `-1` (up), and that the unit test asserts both plus the mask membership — rather than asserting the motion bit is excluded. Verify: `test_mouse_wheel_direction_covers_exposed_and_raw_states` passes.

## 2. Remove the contradiction elsewhere

- [x] 2.1 Grep the repo (`README.md`, `sidebar.py` comments, tests) for any remaining claim that motion reporting is unused, disruptive, or intentionally excluded, and correct or delete it so no statement contradicts the requirement. Verify: no such claim remains outside `openspec/changes/archive/`.

## 3. Verification

- [x] 3.1 Run `python3 -m unittest discover -s tests -v` and confirm the whole suite passes.
- [x] 3.2 Run `openspec validate fix-mouse-motion-requirement --strict` and confirm it passes.
- [x] 3.3 Confirm the behaviour in a real pane: open a document, wheel down and wheel up, and confirm both directions scroll. Automated tests cannot cover this — the bug was that the terminal's event never reached the app.
