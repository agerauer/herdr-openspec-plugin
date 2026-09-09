## Why

Task completion is currently visible only in the detail summary for the selected change, so comparing progress across multiple active changes requires selecting them one at a time. Showing the count in each change row makes overall progress scannable from the primary list.

## What Changes

- Display each active change's completed and total task counts directly in its change-list row using `X/Y` notation.
- Keep the task count associated with the correct row while navigating and highlighting changes.
- Preserve a readable change name and stable layout in narrow sidebars, including changes with no task checklist yet.
- Add rendering coverage for populated, empty, and width-constrained change lists.

## Capabilities

### New Capabilities

- `change-list-task-progress`: Displays per-change task completion counts in the OpenSpec sidebar's change list.

### Modified Capabilities

None.

## Impact

- `sidebar.py`: change-list row rendering and width allocation.
- `tests/test_sidebar.py`: task-count formatting and constrained-width coverage.
- `README.md`: visible change-list information, if the feature overview needs clarification.
- No changes to the OpenSpec file format, Herdr plugin manifest, dependencies, or persisted state.
