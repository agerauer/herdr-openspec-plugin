## 1. Change-row formatting

- [x] 1.1 Add a width-aware change-row formatter that places each change's `tasks_done/tasks_total` value in the row, emits `0/0` when no checklist tasks exist, and verify focused unit tests cover populated and empty counts.
- [x] 1.2 Reserve space for the complete count and truncate long change names without overlap, then verify unit tests cover normal, narrow, and minimum supported sidebar widths.

## 2. Sidebar integration

- [x] 2.1 Use the formatter for every visible change in the sidebar list and apply selection styling to the complete rendered row, then verify navigation still associates each count with the correct change in rendering tests.
- [x] 2.2 Remove the selected-change-only task count from the lower summary to avoid duplicate progress displays, and verify delta summary rendering remains unchanged.

## 3. Documentation and verification

- [x] 3.1 Update the README feature summary to state that task completion appears on each change-list row and verify the documented behavior matches the specification.
- [x] 3.2 Run `python3 -m unittest discover -s tests -v` and perform a live Herdr sidebar smoke test with changes containing tasks and no tasks, verifying the expected `X/Y` values and constrained-width layout.
