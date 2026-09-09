## Purpose

Make the OpenSpec review sidebar foreground the active changes associated with the Git worktree from which the pane was opened.

## ADDED Requirements

### Requirement: Worktree-touched active changes are identified
The sidebar SHALL identify an active change as worktree-touched when any file inside that change directory differs from the current worktree's branch base, including differences introduced by commits after the merge base, staged changes, unstaged changes, and untracked files.

#### Scenario: Change was committed on the worktree branch
- **WHEN** a file under an active change directory differs between the branch merge base and the current worktree HEAD
- **THEN** the sidebar identifies that active change as worktree-touched

#### Scenario: Change has local modifications
- **WHEN** an active change directory contains staged, unstaged, or untracked differences in the current worktree
- **THEN** the sidebar identifies that active change as worktree-touched

#### Scenario: Difference belongs to an archived or unrelated path
- **WHEN** a changed path is outside an active change directory, including under `openspec/changes/archive/`
- **THEN** that path does not cause an active change to be identified as worktree-touched

### Requirement: Worktree-touched changes are prioritized deterministically
The sidebar SHALL sort all worktree-touched active changes ahead of untouched active changes. Within the touched group it SHALL prefer an exact normalized match between the change name and the current branch leaf or worktree directory name, then a hyphen-delimited containment match, then newer change activity, with the change name as the final tie-breaker; untouched changes SHALL remain ordered by change name.

#### Scenario: One touched change matches the branch name
- **WHEN** multiple active changes are worktree-touched and one change name exactly matches the normalized branch leaf
- **THEN** the exact matching change is the first row in the change list

#### Scenario: Multiple touched changes have no name match
- **WHEN** multiple active changes are worktree-touched and none matches the branch leaf or worktree directory name
- **THEN** they are ordered by most recent activity and then by change name

#### Scenario: Touched and untouched changes coexist
- **WHEN** at least one active change is worktree-touched and at least one is untouched
- **THEN** every touched change appears before every untouched change

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
