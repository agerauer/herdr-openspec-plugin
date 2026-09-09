## MODIFIED Requirements

### Requirement: Worktree-touched active changes are identified
The sidebar SHALL identify an active change as worktree-touched when any file inside that change directory differs from the current worktree's branch base, including differences introduced by commits after the merge base, staged changes, unstaged changes, and untracked files. Identification SHALL include change directories under nested OpenSpec roots, using each change's path relative to the Git toplevel.

#### Scenario: Change was committed on the worktree branch
- **WHEN** a file under an active change directory differs between the branch merge base and the current worktree HEAD
- **THEN** the sidebar identifies that active change as worktree-touched

#### Scenario: Change has local modifications
- **WHEN** an active change directory contains staged, unstaged, or untracked differences in the current worktree
- **THEN** the sidebar identifies that active change as worktree-touched

#### Scenario: Nested change has local modifications
- **WHEN** a file under `nxt/openspec/changes/add-login/` differs in the current worktree relative to the branch merge base
- **THEN** the sidebar identifies the nested change displayed as `nxt · add-login` as worktree-touched

#### Scenario: Difference belongs to an archived or unrelated path
- **WHEN** a changed path is outside an active change directory, including under `openspec/changes/archive/` or a nested `openspec/changes/archive/`
- **THEN** that path does not cause an active change to be identified as worktree-touched

### Requirement: Worktree-touched changes are prioritized deterministically
The sidebar SHALL sort all worktree-touched active changes ahead of untouched active changes in the merged list from every discovered OpenSpec root. Within the touched group it SHALL prefer an exact normalized match between the unprefixed OpenSpec change folder name and the current branch leaf or worktree directory name, then a hyphen-delimited containment match, then newer change activity, with the displayed change name as the final tie-breaker; untouched changes SHALL remain ordered by displayed change name.

#### Scenario: One touched change matches the branch name
- **WHEN** multiple active changes are worktree-touched and one unprefixed change folder name exactly matches the normalized branch leaf
- **THEN** the exact matching change is the first row in the change list even if that change is displayed with a nested prefix

#### Scenario: Multiple touched changes have no name match
- **WHEN** multiple active changes are worktree-touched and none matches the branch leaf or worktree directory name
- **THEN** they are ordered by most recent activity and then by displayed change name

#### Scenario: Touched and untouched changes coexist
- **WHEN** at least one active change is worktree-touched and at least one is untouched
- **THEN** every touched change appears before every untouched change regardless of which OpenSpec root each change comes from

#### Scenario: Untouched nested and root changes are ordered by displayed name
- **WHEN** no active change is worktree-touched and the merged list contains `zeta`, `nxt · add-api`, and `add-login`
- **THEN** the change list order is `add-login`, `nxt · add-api`, `zeta`

## ADDED Requirements

### Requirement: Selection identity uses the displayed change name
The sidebar SHALL preserve and restore the selected change using its displayed name so two OpenSpec roots that share a folder name remain distinct across reloads.

#### Scenario: Refresh preserves a nested selection when a root change shares the folder name
- **WHEN** the selected row is `nxt · add-login` and a root-level `add-login` change also exists
- **THEN** a refresh keeps `nxt · add-login` selected
