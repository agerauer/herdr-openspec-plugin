## Context

The sidebar process receives the invoking OpenSpec project through `OPENSPEC_PROJECT`, even though its process runs from the plugin checkout. `discover_changes` currently scans `openspec/changes/` alphabetically and returns `Change` models without repository metadata; `Sidebar.reload` preserves an existing selection by change name but an initial load starts at index zero. See `proposal.md` for motivation and `specs/worktree-change-prioritization/spec.md` for required behavior.

The implementation must remain dependency-free, avoid making Git failures fatal, and keep the two-second refresh loop responsive in repositories with many unrelated paths.

## Goals / Non-Goals

**Goals:**

- Produce one testable worktree snapshot that maps active change names to touch state, ranking signals, and activity time.
- Keep Git inspection limited to `openspec/changes/` and bounded by short subprocess timeouts.
- Preserve the selected change by name after the sidebar has completed its initial load.
- Make selected and worktree-associated states simultaneously legible in narrow rows.

**Non-Goals:**

- Determining which human authored a proposal from Git author metadata.
- Filtering untouched changes out of the sidebar.
- Adding user configuration for base refs, ranking weights, or highlight appearance.
- Watching other worktrees or comparing active changes across worktree filesystems.
- Changing Herdr pane placement, OpenSpec discovery rules, or task progress calculation.

## Decisions

### Compare the current worktree to a resolved default-branch merge base

Git inspection will run with the selected OpenSpec project as its working directory. The base-ref resolver will try the remote default branch, then conventional `origin/main`, local `main`, `origin/master`, and local `master` refs, ignoring a candidate that cannot resolve. The snapshot will compare the working tree against `merge-base HEAD <base-ref>` so the resulting path set includes committed branch differences plus staged and unstaged tracked differences. A separate scoped untracked-file query will add new files that ordinary diff output omits.

Only paths whose first components are `openspec/changes/<active-name>/` will be associated with an active change; `archive` and paths outside the active change set will be ignored. If repository detection, base resolution, merge-base, diff, or untracked-file collection fails or times out, the snapshot will be unavailable and discovery will use its existing normal ordering.

Alternative considered: use the current branch's upstream. A feature branch upstream often points to the remote copy of the same feature branch, which would hide already-pushed worktree commits instead of identifying everything added since the default branch.

### Keep Git collection separate from OpenSpec parsing

Introduce a small immutable worktree snapshot and pure helpers for path-to-change association and ranking. `discover_changes` will accept the optional snapshot, attach its results to each `Change`, and sort after all OpenSpec metadata has been parsed. This keeps filesystem parsing usable and testable without Git and makes fallback an explicit `None` path rather than exception-driven behavior throughout rendering.

The periodic reload fingerprint will incorporate the snapshot identity (resolved HEAD/base plus scoped changed paths) so a commit, checkout, or base change can reorder/highlight rows even when file timestamps alone do not expose the transition. Git commands will remain scoped and use short timeouts; a failed refresh will fall back without terminating the TUI.

Alternative considered: call Git once per change during discovery. Per-directory subprocesses scale poorly and can yield an inconsistent view if repository state changes between calls.

### Rank touched changes with discrete name affinity before recency

For each touched change, ranking will use a tuple with these priorities: exact normalized equality with the branch leaf or worktree directory basename; full change-name containment at hyphen-delimited boundaries; most recent activity; and case-insensitive change name. Activity will be the latest available timestamp from touched files and the latest branch commit affecting the change path. All untouched changes will follow the touched group in their existing case-insensitive name order.

The highest-ranked touched item therefore occupies index zero and becomes the initial selection naturally. `reload` will continue resolving an already selected name after re-sorting, preventing periodic Git refreshes from stealing selection.

Alternative considered: select only by latest modification time. Checkout and rebase operations can refresh many mtimes together, while branch/worktree names commonly provide a stronger intent signal.

### Use separate selection and worktree markers in the formatted row

The fixed-width change-row formatter will reserve adjacent positions for the existing selection arrow and a worktree marker. A touched selected row will show both, while color/bold styling provides a secondary accent. Name truncation will continue yielding to the complete `X/Y` task count.

Alternative considered: color alone. Terminal themes and reverse-video selection can erase a color-only distinction, so a stable marker is needed as the primary signal.

## Risks / Trade-offs

- [Repositories whose primary branch is not exposed through a conventional local or remote ref cannot produce a reliable committed-work comparison] → fail open to normal ordering instead of guessing from arbitrary ancestry.
- [Scoped Git inspection still adds work to the refresh loop] → collect one snapshot per refresh, scope every path query, apply short timeouts, and reuse the result for all changes.
- [A change copied or modified on a branch can be highlighted even if originally authored elsewhere] → describe the signal as “touched in this worktree”; do not claim Git authorship identity.
- [Branch names may match multiple change names] → use discrete affinity tiers, recency, and lexical tie-breaking for deterministic results.
- [Additional row markers reduce name width] → preserve the full task count and apply the existing ellipsis behavior to the name.

## Migration Plan

No data migration is required. Reopening the linked plugin pane loads worktree-aware ordering automatically. Rollback consists of reverting the sidebar model and rendering changes; OpenSpec artifacts and repository history remain unchanged.
