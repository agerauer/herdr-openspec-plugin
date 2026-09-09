## Why

The sidebar currently walks up from the invoking pane until it finds the nearest `openspec/` directory and then lists only that project's `openspec/changes/`. In a monorepo that keeps a root OpenSpec tree plus package-level trees (for example `nxt/openspec`), reviewers only see one of those inventories and have to change directories to inspect the rest.

## What Changes

- Treat the Git workspace (or, when Git is unavailable, the invoking directory) as the search root and discover every `openspec/` directory at that root and at most two directory levels below it.
- Show one merged change list drawn from all discovered OpenSpec roots.
- Prefix each nested change with the OpenSpec project's path relative to the search root, using a spaced middle dot (` · `) as the separator (for example `nxt · add-login`). Root-level changes keep their unprefixed OpenSpec change name.
- Apply the existing worktree-first ranking, including affinity, recency, and name order, to that merged list.
- Keep validate, edit, artifact loading, and refresh watching scoped to the originating OpenSpec root for each selected change.

## Capabilities

### New Capabilities

- `nested-openspec-discovery`: Defines how the sidebar finds multiple OpenSpec roots in a workspace, merges their active changes, and displays nested changes with a middle-dot project prefix.

### Modified Capabilities

- `worktree-change-prioritization`: Worktree touch detection, ranking, and selection preservation must operate on the merged multi-root list, including nested `openspec/changes/` paths and prefixed display names.

## Impact

- `scripts/open_sidebar.py`: resolve a workspace search root instead of stopping at the nearest `openspec/` parent.
- `sidebar.py`: multi-root discovery, prefixed change identities, merged sorting, worktree path association, fingerprinting, empty-state detection, and per-root validate/edit working directories.
- `tests/test_sidebar.py`: coverage for nested discovery, prefixing, skip rules, merged ranking, nested worktree paths, and per-root operations.
- `README.md`: document multi-root discovery and prefixed nested change names.
- No OpenSpec file-format changes, Herdr API changes, or new runtime dependencies.
