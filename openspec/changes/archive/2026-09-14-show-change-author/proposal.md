## Why

The change list says what each change is and how far along it is, but not **whose** it is. On a shared repository that is the first thing a reviewer wants when scanning the list — which of these are mine, and who should I ask about the rest. The information is already in the repository: the commit that first added a change's folder carries its author, and in this project (and on GitHub generally) that author's email encodes their GitHub login, so the attribution can be resolved locally without a network call.

## What Changes

- Each change card SHALL show the change's creator next to its name, as `‹name› · ‹author›`.
- The author is resolved from the commit that first added the change's folder: the GitHub login when the commit email is a GitHub noreply address (`20586+agerauer@users.noreply.github.com` → `agerauer`), otherwise the commit author's name.
- A change with no creating commit — not yet committed, which is the normal state while a change is being worked on — SHALL show `local` rather than an author, so "not yet attributable" is visibly distinct from "authored by you".
- A change in a directory that is not a Git worktree, or where the Git query fails or times out, SHALL show no author at all and the card SHALL otherwise render unchanged.
- The change name keeps priority for the available width: when the card is too narrow for both, the author is dropped rather than the name truncated further.

## Capabilities

### New Capabilities
- `change-authorship`: resolving who created each change from repository history, including the GitHub-login derivation, the uncommitted and non-Git fallbacks, and doing it without a network call.

### Modified Capabilities
- `sidebar-navigation`: the "Change rows render as inline cards" requirement describes the card's name line, which now also carries the author; and its clickable-name target stays on the name rather than extending over the author.

## Impact

- `sidebar.py`: a bulk per-OpenSpec-root Git query resolving every change's creating author in one call, refreshed on the existing reload cycle rather than per card; pure helpers to parse that output and to derive a GitHub login from an email; the author rendered after the name in `draw_change_card`.
- `tests/test_sidebar.py`: unit tests for the login derivation and the history parsing (both pure), plus card-rendering tests for the author, the `local` fallback, the no-Git case, and the narrow-width drop.
- `README.md`: note that cards show who created each change.
- No new dependencies and no network access: `gh` and the GitHub API are deliberately not used (see design.md).

### Assumption recorded

- **Creator, not last editor.** "Created" is read literally: the author of the commit that first added the change folder, not whoever most recently touched it.
