## 1. Worktree snapshot

- [x] 1.1 Add bounded Git command and default-branch/merge-base resolution helpers, and verify unit tests cover remote-default, `main`/`master` fallback, non-repository, command failure, and timeout results.
- [x] 1.2 Collect one scoped snapshot of committed, staged, unstaged, and untracked paths under `openspec/changes/`, and verify temporary Git repository tests identify each source without including archived or unrelated paths.
- [x] 1.3 Map snapshot paths and latest file/commit activity to active change names, and verify pure tests cover nested artifacts, duplicate paths, missing directories, and deterministic timestamps.

## 2. Prioritization and selection

- [x] 2.1 Extend the change model with worktree touch and activity metadata, implement exact/containment/recency/name ranking, and verify unit tests cover every rank tier plus touched-before-untouched ordering.
- [x] 2.2 Integrate the optional snapshot into discovery and the refresh fingerprint so initial load selects the highest-ranked touched change while later reloads preserve an existing selected name, and verify tests cover initial selection, reorder after Git state changes, removed selections, and Git-unavailable fallback.

## 3. Worktree highlighting

- [x] 3.1 Reserve distinct selection and worktree markers in fixed-width change rows while retaining the complete `X/Y` count, and verify formatting tests cover touched, selected, touched-and-selected, untouched, long-name, and minimum-width rows.
- [x] 3.2 Apply a visible worktree accent to every touched row without breaking selection or row hit targets, and verify rendering tests cover multiple highlighted rows and a highlighted selected row.

## 4. Documentation and integration verification

- [x] 4.1 Update the README to explain worktree-aware top sorting, highlighting, initial selection, comparison-base behavior, and graceful fallback, and verify its description matches the implemented ranking signals.
- [x] 4.2 Run `python3 -m unittest discover -s tests -v`, validate the OpenSpec change, and perform a live Herdr smoke test from a linked worktree containing multiple touched and untouched changes to verify ordering, highlighting, preselection, and selection preservation after refresh.
