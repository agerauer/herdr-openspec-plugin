## 1. Resolve authorship (pure helpers)

- [x] 1.1 Add a pure function deriving a display author from a commit email and name: `<digits>+<login>@users.noreply.github.com` and `<login>@users.noreply.github.com` both yield `login`; any other domain yields the commit author's name. Unit-test all three forms plus an empty/absent email.
- [x] 1.2 Add a pure parser for `git log --diff-filter=A --format='C|%ae|%an' --name-only` output that maps each change folder name to its creating author. Git lists newest-first, so a later-parsed (older) commit for the same folder SHALL win. Unit-test: single change; a folder touched by several commits resolving to the earliest; paths under `archive/` ignored; malformed or empty input yielding an empty mapping.

## 2. Collect and attach the author

- [x] 2.1 Add the bulk lookup that runs the query above once per OpenSpec root via `run_git` and returns the parsed mapping, with `None` from `run_git` (not a worktree, failure, timeout) yielding an empty mapping. Verify with a fake runner that no per-change subprocess is issued — one call per root.
- [x] 2.2 Attach the resolved author to each discovered change during the reload scan, keeping each change's lookup within its own OpenSpec root. Distinguish the three outcomes from the design: a resolved author; `local` when the root is a Git worktree but the change has no creating commit; and no author at all when there is no worktree or the query failed. Verify: a temp repo with one committed and one uncommitted change yields an author and `local` respectively, and a non-Git directory yields neither.

## 3. Render it beside the name

- [x] 3.1 Draw the author after the change name as `‹name› · ‹author›`, as a separate `put` styled less prominently than the name (the name keeps its existing bold/worktree colour). Omit the author entirely when the pane is too narrow for both, never truncating the name further to fit it.
- [x] 3.2 Keep the clickable-name hit target spanning only the name's own text, so clicking the author selects the change without opening the Proposal. Verify against the existing name-click tests plus a new click on the author's columns.

## 4. Tests for observable behavior

- [x] 4.1 Card shows `name · author` for a change with a resolved author, with the author drawn in a less prominent style than the name.
- [x] 4.2 Card shows `local` for an uncommitted change, and no author at all for a change whose root is not a Git worktree.
- [x] 4.3 At a narrow width the author is omitted and the name is not shortened to make room for it.
- [x] 4.4 Clicking the author beside a name selects the change and opens nothing; clicking the name still opens the Proposal.

## 5. Docs and verification

- [x] 5.1 Update `README.md` to note that each card shows who created the change, including the `local` marker for a change that is not yet committed.
- [x] 5.2 Run `python3 -m unittest discover -s tests -v` and confirm the whole suite passes, including the existing card-rendering, name-click, and agent-button tests.
- [x] 5.3 Run `openspec validate show-change-author --strict` and confirm it passes.
