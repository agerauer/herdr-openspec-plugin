## Why

OpenSpec repositories used through Herdr often contain active changes from several branches or worktrees, while the reviewer normally cares first about the proposal being developed in the invoking worktree. The sidebar currently sorts every change alphabetically and initially selects the first one, so the relevant change can be buried and requires manual identification.

## What Changes

- Detect active OpenSpec change directories whose contents differ in the current Git worktree relative to its branch base, including committed, staged, unstaged, and untracked files.
- Sort worktree-touched changes ahead of untouched active changes while keeping ordering deterministic within both groups.
- On initial pane open, preselect the most likely worktree change using branch/worktree-name affinity and recency as deterministic ranking signals.
- Visually distinguish every worktree-touched change without obscuring the selected-row treatment or the existing task count.
- Preserve the current stable list behavior when the project is not a Git worktree or a comparison base cannot be resolved.

## Capabilities

### New Capabilities

- `worktree-change-prioritization`: Defines how the sidebar identifies, orders, highlights, and initially selects active changes associated with the current Git worktree.

### Modified Capabilities

None.

## Impact

- `sidebar.py`: Git worktree inspection, per-change worktree metadata, ranking, initial selection, and row highlighting.
- `tests/test_sidebar.py`: Git fixture coverage for committed and local changes, ranking, fallback behavior, and row formatting.
- `README.md`: explanation of worktree-aware ordering, highlighting, and initial selection.
- The implementation remains dependency-free and uses the installed Git CLI; no OpenSpec file formats or Herdr APIs change.
