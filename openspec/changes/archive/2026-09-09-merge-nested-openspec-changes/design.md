## Context

`scripts/open_sidebar.py` and `sidebar.find_project` both stop at the nearest ancestor that contains `openspec/`, then `discover_changes` reads only `<project>/openspec/changes/`. Worktree inspection is likewise scoped to the pathspec `openspec/changes` and associates Git paths whose first two parts are `openspec/changes`. `Change.name` is the folder name and is reused for display, ranking, selection preservation, and `openspec validate`. See `proposal.md` for motivation and `specs/nested-openspec-discovery/spec.md` plus `specs/worktree-change-prioritization/spec.md` for required behavior.

The implementation must remain dependency-free, keep the two-second refresh loop responsive in large monorepos, and continue failing open when Git is missing.

## Goals / Non-Goals

**Goals:**

- Resolve one workspace search root and discover OpenSpec projects at that root and at most two directory levels below it.
- Give each change a stable displayed identity that prefixes nested projects with middle-dot relative paths.
- Reuse the existing worktree snapshot, ranking, and selection flow on the merged list.
- Run validate and edit against the originating OpenSpec project, not the search root.

**Non-Goals:**

- Changing OpenSpec CLI discovery, schemas, or file layouts.
- Merging or comparing specs across OpenSpec roots.
- Configurable include/exclude globs, user-defined depth limits, or per-package filters.
- Watching OpenSpec trees outside the resolved search root (other worktrees, sibling checkouts).
- Altering Herdr pane placement, task-progress rendering, or mouse/keyboard navigation.

## Decisions

### Resolve a workspace search root, then scan down

The pane action will pass a search root through `OPENSPEC_PROJECT` instead of the nearest OpenSpec parent. Resolution order:

1. Git toplevel of the invoking pane directory, when `rev-parse --show-toplevel` succeeds inside a worktree.
2. Otherwise the highest ancestor that has `openspec/` as a direct child.
3. Otherwise the invoking directory.

The sidebar will treat that path as the workspace root and discover OpenSpec projects beneath it. `find_project` remains as a compatibility helper for locating a single `openspec/` child, but listing no longer stops there.

Alternative considered: keep nearest-parent resolution and only scan its descendants. That still hides a root `openspec/` when the pane is opened from `nxt/`, which is the monorepo case that motivates the change.

### Walk at most two directory levels with a small skip set

Discovery will look for a child named `openspec` at the search root and at directories one or two levels below it. That includes `openspec/`, `nxt/openspec/`, and `apps/nxt/openspec/`, and excludes `apps/nxt/web/openspec/`. It will not follow symlinks, will not descend into an `openspec/` directory, and will skip `.git`, `node_modules`, `__pycache__`, `venv`, `.venv`, `dist`, `build`, `target`, `coverage`, and any other directory whose name starts with `.`. An OpenSpec project is the parent of a discovered `openspec/` directory.

The depth cap is the primary bound for large monorepos; the skip set still hides vendor and hidden trees that sit within those two levels. Roots deeper than two levels are intentionally invisible.

Alternative considered: unbounded recursion with only a skip set. That can still walk enormous package graphs. A fixed two-level cap matches typical `packages/<name>/openspec` layouts without scanning the rest of the tree.

### Separate folder name, display name, and originating project

Extend the change model so listing, ranking, and operations do not overload one string:

- `folder_name`: OpenSpec change directory name (`add-login`), used for `openspec validate` and worktree name affinity.
- `name`: displayed identity (`nxt · add-login` or `add-login`), used for rows, lexical sort, and selection preservation.
- `project`: originating OpenSpec project directory (`<search-root>/nxt`), used as `cwd` for validate/edit and as the base for artifact paths.

Prefix construction: relative POSIX path from search root to `project`, with `/` replaced by ` · ` (spaced U+00B7 MIDDLE DOT), matching the existing `Spec ·` artifact labels. Empty relative path means the search-root OpenSpec tree and produces no prefix.

Existing helpers that key worktree activity by change folder name will key by displayed name (or `(project, folder_name)`) so two `add-login` trees do not share touch state.

Alternative considered: keep `name` as the folder name and add a separate label only in the renderer. Selection preservation and worktree maps would still collide across roots.

### Collect one Git snapshot from the search root with per-root pathspecs

`collect_worktree_snapshot` will run Git at the search root (Git toplevel) and pass every discovered `<relative-project>/openspec/changes` pathspec instead of a single `openspec/changes`. Path association will treat a relative path as an active change when some suffix is `openspec/changes/<active-folder>/...` and the prefix before `openspec` matches a discovered project. Archive and dot-prefixed folders remain excluded.

Activity and ranking stay in the current snapshot helpers, keyed by displayed name. Affinity continues to use `folder_name` so a branch leaf `add-login` still matches `nxt · add-login`. Lexical tie-breaking and untouched order use `name`.

The refresh fingerprint will hash files under every discovered `openspec/changes/` tree plus the snapshot identity, so nested edits trigger reload.

Alternative considered: one Git snapshot per OpenSpec project. That multiplies subprocesses on each refresh and can observe inconsistent HEAD/merge-base state between calls.

### Empty state and operations follow discovery results

"No OpenSpec project" is shown only when discovery returns no roots. "No active changes" is shown when roots exist but the merged active list is empty. Validate uses `["openspec", "validate", folder_name, "--no-interactive"]` with `cwd=change.project`. Artifact open/edit already use absolute paths on the `Change` and stay valid once those paths come from nested roots.

## Risks / Trade-offs

- [Walking a huge monorepo can slow the first load and each fingerprint] → stop after two directory levels, skip well-known heavy directories, do not follow symlinks, do not recurse into `openspec/`, and keep Git pathspecs scoped to discovered change trees.
- [An OpenSpec tree three or more levels down is invisible] → keep the depth cap fixed at two; do not add configuration in this change.
- [A skipped `node_modules/openspec` or hidden tree is invisible] → document the skip set; do not add ignore-file configuration in this change.
- [Prefixed names are longer and truncate sooner in narrow rows] → keep the existing ellipsis-vs-`X/Y` formatter; truncation already yields to task progress.
- [Branch affinity uses the unprefixed folder name, so two nested changes with the same folder name can share an exact match] → recency and displayed-name tie-break still produce a deterministic winner; both rows remain visible.
- [Passing the Git toplevel as `OPENSPEC_PROJECT` changes pane identity tokens] → existing panes keyed by nearest-parent project will not be reused across that identity change; a newly opened pane uses the workspace root. Rollback restores nearest-parent identity.

## Migration Plan

No data migration is required. Relink or reopen the plugin pane to load multi-root discovery. Rollback is a revert of the sidebar model, opener search-root resolution, tests, and README; OpenSpec artifacts on disk are unchanged.

## Open Questions

None. Search-root fallback, two-level depth cap, skip set, prefix format, and affinity-vs-display-name ranking are specified above and in the delta specs.
