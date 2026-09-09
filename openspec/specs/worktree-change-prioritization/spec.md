# Worktree Change Prioritization Specification

## Purpose

Make the OpenSpec review sidebar foreground the active changes associated with the Git worktree from which the pane was opened.

## Requirements

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

### Requirement: Initial selection favors the most likely worktree change
On the first load of a newly opened sidebar, the sidebar SHALL select the highest-ranked worktree-touched change. If no active change is identified as worktree-touched, it SHALL retain the existing first-change selection behavior.

#### Scenario: Sidebar opens with touched changes
- **WHEN** the sidebar first loads and one or more active changes are worktree-touched
- **THEN** the first and selected row is the touched change with the highest deterministic rank

#### Scenario: Selected change remains active during refresh
- **WHEN** an already open sidebar refreshes and its selected change still exists
- **THEN** the sidebar preserves that selection even if worktree ranking data changes

#### Scenario: No touched change can be identified
- **WHEN** the project has active changes but none is identified as worktree-touched
- **THEN** the sidebar selects the first change in the normal deterministic order

### Requirement: Every touched change is visually highlighted
Each visible worktree-touched change row SHALL include a dedicated visual marker or accent, and that treatment SHALL remain distinguishable while the row is selected without hiding its change name or `X/Y` task count.

#### Scenario: Multiple touched changes are visible
- **WHEN** two or more worktree-touched changes appear in the visible change window
- **THEN** every one of their rows displays the worktree highlight

#### Scenario: Touched change is selected
- **WHEN** a worktree-touched change is also the selected row
- **THEN** both its worktree association and selection state remain visually discernible and its task count remains visible

### Requirement: Missing Git context has a safe fallback
The sidebar SHALL continue to list active changes without worktree highlights when the project is not inside a Git worktree, Git is unavailable, or no comparison base can be resolved, and the inability to calculate worktree association SHALL NOT prevent the pane from opening.

#### Scenario: Project is not a Git worktree
- **WHEN** the sidebar opens for an OpenSpec project that is not inside a Git worktree
- **THEN** active changes use the normal deterministic ordering and initial selection without worktree highlights

#### Scenario: Git inspection fails
- **WHEN** a Git command used to determine the worktree association fails or times out
- **THEN** the sidebar remains usable and falls back to normal deterministic ordering without reporting a fatal error

### Requirement: Selection identity uses the displayed change name
The sidebar SHALL preserve and restore the selected change using its displayed name so two OpenSpec roots that share a folder name remain distinct across reloads.

#### Scenario: Refresh preserves a nested selection when a root change shares the folder name
- **WHEN** the selected row is `nxt · add-login` and a root-level `add-login` change also exists
- **THEN** a refresh keeps `nxt · add-login` selected
