## 1. Derived state

- [x] 1.1 Add `Change.state` computing INVALID (validation failed) → DRAFT (`0/0` or `missing_required`) → READY (`0/Y`) → IN PROGRESS (`X/Y`) → DONE (`Y/Y`); verify unit tests covering each branch, including openspec-draft with some tasks done resolving to DRAFT and failed validation resolving to INVALID regardless of counts

## 2. Card rendering

- [x] 2.1 Rewrite `format_card_status` to return `STATE · done/total · N Artifacts`, reserving the state and complete `done/total` before the artifact count when the line is too narrow; verify unit tests for the full-width string and for a constrained width that keeps state + `done/total` and trims the artifact count
- [x] 2.2 Update `draw_change_card` to color the leading state by a state→color map (INVALID red, DRAFT dim, READY cyan, IN PROGRESS yellow, DONE green) instead of the raw openspec status; verify a headless draw test that a valid `x/y` change shows `IN PROGRESS` in the in-progress color and a `y/y` change shows `DONE` in the done color

## 3. Tests and docs

- [x] 3.1 Update existing status-line/card tests for the new order and the derived state, and confirm the raw openspec status is no longer shown as a separate token; verify `python3 -m unittest discover -s tests` passes
- [x] 3.2 Update `README.md` to describe the derived change state (draft/ready/in-progress/done/invalid) and its colors on the card; verify the README no longer implies a raw `READY` status token
