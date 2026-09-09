## 1. Search root and OpenSpec discovery

- [x] 1.1 Add search-root resolution that prefers Git toplevel, then the highest ancestor with a direct `openspec/` child, then the invoking directory, and verify unit tests cover a Git monorepo opened from `nxt/src`, a Git-unavailable tree with both root and nested `openspec/` dirs, and a directory with no OpenSpec ancestors.
- [x] 1.2 Discover `openspec/` projects at the search root and at most two directory levels below it, with the skip set, no symlink follow, and no descent into `openspec/` itself, and verify tests include root-plus-`nxt`, `apps/nxt/openspec`, exclusion of `apps/nxt/web/openspec`, subdirectory-only trees, `node_modules`/hidden/in-`openspec` skips, and empty-root omission.
- [x] 1.3 Point `scripts/open_sidebar.py` at the workspace search root instead of the nearest OpenSpec parent, and verify tests cover a pane opened from a nested package receiving the Git toplevel.

## 2. Prefixed merged change list

- [x] 2.1 Extend the change model with `folder_name`, displayed `name`, and originating `project`, and verify existing change-row, task-progress, and selection tests still pass with unprefixed root changes.
- [x] 2.2 Merge active changes from every discovered root, prefix nested names as `<relative-project> · <folder-name>` using a spaced middle dot, leave root changes unprefixed, and verify tests cover `nxt · add-login`, `apps · nxt · add-login`, unprefixed root `add-login`, duplicate folder names across roots, omission of a three-level-deep change, and a single nested change when the root tree is empty.
- [x] 2.3 Apply existing untouched name order to displayed names on the merged list, and verify that `zeta`, `nxt · add-api`, and `add-login` sort as `add-login`, `nxt · add-api`, `zeta` when no worktree snapshot is present.

## 3. Worktree association and ranking

- [x] 3.1 Collect one worktree snapshot from the search root using a pathspec per discovered `openspec/changes` tree, associate nested Git paths with displayed names, ignore nested archives, and verify temporary Git repository tests cover `nxt/openspec/changes/add-login` touches plus ignored `nxt/openspec/changes/archive/` paths.
- [x] 3.2 Rank the merged list with existing touched-first order, affinity on `folder_name`, recency, and displayed-name tie-break, and verify tests cover a prefixed change matching the branch leaf, mixed-root touched-before-untouched order, and displayed-name ordering when nothing matches.
- [x] 3.3 Preserve selection by displayed name across reload, fingerprint every discovered change tree, and verify a refresh keeps `nxt · add-login` selected when a root-level `add-login` also exists.

## 4. Operations and empty state

- [x] 4.1 Run `openspec validate` with the unprefixed folder name and `cwd` of the originating project, load nested artifact paths from that change directory, and verify tests cover validate args/cwd for `nxt · add-login` plus opening `nxt/openspec/changes/add-login/proposal.md`.
- [x] 4.2 Show "No OpenSpec project" only when discovery finds no roots and "No active changes" when roots exist but the merged list is empty, and verify both empty-state paths.

## 5. Documentation and verification

- [x] 5.1 Update the README to describe workspace-wide OpenSpec discovery limited to two directory levels, middle-dot nested prefixes, merged-list sorting, and per-root validate/edit, and verify the description matches the implemented prefix, depth cap, and search-root rules.
- [x] 5.2 Run `python3 -m unittest discover -s tests -v`, validate the OpenSpec change, and perform a live Herdr smoke test in a fixture or worktree that has both a root change and a nested `nxt` change.
