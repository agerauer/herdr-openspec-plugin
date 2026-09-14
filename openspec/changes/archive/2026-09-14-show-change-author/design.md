## Context

See proposal.md — Why. Mechanically: the sidebar already shells out to Git through `run_git(project, args)`, a bounded read-only helper that returns `None` on non-zero exit, timeout, or `OSError`. `collect_worktree_snapshot` uses that pattern to gather branch/diff facts once per reload, and `reload()` only re-scans when a fingerprint over `openspec/changes/` changes, so per-reload Git work is already the established shape. Changes may come from several OpenSpec roots (`discover_openspec_projects`), and an existing requirement keeps each change's operations in its originating root.

The card's first line is drawn by `draw_change_card` as a single `put` of `format_card_name(change, width - 2, selected)`, and `make-change-titles-clickable` registers a hit target spanning exactly that drawn string.

## Goals / Non-Goals

**Goals:**
- Attribute each active change to its creator without a network call, and without a Git process per change.
- Keep the change list rendering unchanged when Git is unavailable or slow.

**Non-Goals:**
- Attribution for archived changes (the card list shows active changes only).
- Last-editor or contributor lists — creator only (see the proposal's recorded assumption).
- Resolving a GitHub login for an email that does not encode one; no directory lookup, no `gh`.

## Decisions

### One `git log` per OpenSpec root, not per change
Resolve every change's creator in a single query per root:

```
git log --diff-filter=A --format='C|%ae|%an' --name-only -- <root>/openspec/changes
```

Git walks newest-first, so for each change folder the **last** block naming a file under it is the commit that created it. Parsing keeps overwriting the entry per folder and naturally ends on the earliest. Measured on this repository the whole history of the changes tree is ~90 lines, so one bounded call covers every change.

- *Alternative — `git log --diff-filter=A` per change folder:* N subprocesses per reload, each paying process start plus a history walk; with a dozen changes that is the difference between one bounded call and a dozen. Rejected.
- *Alternative — `git log --follow`:* does not work on directories, and we do not need rename tracking: a change is attributed at its active path, and archiving is a separate concern.

Run it alongside the existing worktree snapshot, cached for the reload cycle, so the cost lands where `reload()` already pays for Git rather than on every frame. `run_git` returning `None` (not a worktree, failure, timeout) yields an empty mapping and therefore no authors — the required degradation.

### Parse the GitHub login from the email, not from a service
GitHub noreply addresses take the form `<id>+<login>@users.noreply.github.com` and, for older accounts, `<login>@users.noreply.github.com`. Take the local part, drop a leading `<digits>+` when present, and use the remainder as the login when the domain matches; otherwise fall back to the commit author's name. This is a pure string function, exhaustively unit-testable, and it is the only step that could have justified a network call.

- *Alternative — `gh api` to resolve a login for any email:* accurate for ordinary addresses too, but it adds an auth requirement, network latency and failure modes to a pane that redraws offline on a timer, for a decorative field. Explicitly rejected; the requirement states resolution is local.

### `local` is a resolution outcome, not a missing value
Three distinct outcomes must stay distinguishable, so model them as such rather than as an optional string:
- a resolved author (login or name) — the change was committed;
- `local` — the root is a Git worktree but this change has no creating commit;
- nothing at all — no worktree, or the query failed.

Deriving `local` from "root is a worktree" rather than from "lookup returned nothing" is what keeps the failure case from masquerading as an uncommitted change.

### Draw the author as its own span, after the name
`put` takes one attribute per call, and the author must be less prominent than the name, so the first card line becomes: `put` the name with its existing style, then `put` the separator and author dimmed. The hit target registered by `make-change-titles-clickable` keeps spanning **only** the name's own text, so clicking the author falls through to the card-wide select target — which is why that behaviour gets its own scenario in the spec delta.

Width priority mirrors the status line's existing treatment of the action button, but inverted in emphasis: there the button's width is reserved first and the status text yields; here the **name** wins and the author is dropped whole when it does not fit. A half-truncated username is worse than none.

## Risks / Trade-offs

- **History-walk cost on a large repository.** One call per root per reload, bounded by the existing Git timeout; on timeout the list renders without authors. If it ever bites, the mapping can be cached against the fingerprint instead of recomputed.
- **Author is only as good as the commit.** A change committed by someone rebasing or squashing another person's work is attributed to the commit author. Accepted: it matches what `git log` reports, and the field is informational.
- **`local` is per-worktree, not per-person.** Two people with uncommitted changes each see their own as `local`; that is the intent of the placeholder rather than a limitation to solve.
