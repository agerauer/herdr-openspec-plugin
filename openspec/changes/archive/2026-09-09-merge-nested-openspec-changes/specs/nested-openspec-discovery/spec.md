## Purpose

Find OpenSpec projects at the workspace root and at most two directory levels below it, and present their active changes in one prefixed, merged list.

## ADDED Requirements

### Requirement: Search root covers the workspace
The sidebar SHALL treat the Git toplevel as the search root when the invoking directory is inside a Git worktree. When Git is unavailable or the invoking directory is not inside a worktree, it SHALL use the highest ancestor that contains an `openspec/` directory as a direct child, or the invoking directory if no such ancestor exists.

#### Scenario: Invoking pane is inside a Git monorepo
- **WHEN** the invoking directory is `nxt/src` inside a Git worktree whose toplevel also contains `openspec/` and `nxt/openspec/`
- **THEN** the search root is the Git toplevel rather than the nearest `openspec/` parent

#### Scenario: Git is unavailable
- **WHEN** Git cannot identify a toplevel and both the workspace root and a subdirectory contain an `openspec/` directory
- **THEN** the search root is the highest ancestor that has `openspec/` as a direct child

### Requirement: Nested OpenSpec directories are discovered
The sidebar SHALL discover every `openspec/` directory at the search root and at most two directory levels below it, excluding skipped directories and without following symbolic links or descending into an `openspec/` directory itself. An `openspec/` directory three or more levels below the search root SHALL be ignored.

#### Scenario: Root and subdirectory both contain OpenSpec
- **WHEN** the search root contains `openspec/changes/` and `nxt/openspec/changes/`
- **THEN** both OpenSpec roots are included in discovery

#### Scenario: Two-level subdirectory contains OpenSpec
- **WHEN** the search root contains `apps/nxt/openspec/changes/`
- **THEN** that OpenSpec root is included in discovery

#### Scenario: Only subdirectory trees contain OpenSpec
- **WHEN** the search root has no `openspec/` directory and two first-level subdirectories each contain `openspec/changes/`
- **THEN** both subdirectory OpenSpec roots are included in discovery

#### Scenario: OpenSpec directory is more than two levels deep
- **WHEN** an `openspec/` directory exists at `apps/nxt/web/openspec/` and no `openspec/` directory exists at a shallower path in that tree
- **THEN** that directory is not treated as an OpenSpec root

#### Scenario: Skipped vendor or hidden directories
- **WHEN** an `openspec/` directory exists under `node_modules`, `.git`, another hidden directory, or inside an already discovered `openspec/` tree
- **THEN** that directory is not treated as an OpenSpec root

### Requirement: Active changes are shown in one merged list
The sidebar SHALL list every active change from every discovered OpenSpec root in a single change list. Archived directories and dot-prefixed directories SHALL remain excluded from each root.

#### Scenario: Changes exist in multiple roots
- **WHEN** the root OpenSpec tree has an active change `add-login` and `nxt/openspec` has an active change `add-api`
- **THEN** the change list contains both changes

#### Scenario: One root has no active changes
- **WHEN** the root OpenSpec tree has no active changes and a subdirectory OpenSpec tree has one active change
- **THEN** the change list contains that subdirectory change and omits empty roots

### Requirement: Nested changes display a middle-dot project prefix
The sidebar SHALL display a nested change as `<project-prefix> · <change-name>`, where `<project-prefix>` is the OpenSpec project's path relative to the search root with `/` replaced by ` · `. A change from an `openspec/` directory at the search root SHALL keep its unprefixed OpenSpec change name.

#### Scenario: First-level subdirectory change
- **WHEN** an active change `add-login` exists under `nxt/openspec/changes/`
- **THEN** its change-list row displays `nxt · add-login`

#### Scenario: Nested subdirectory change
- **WHEN** an active change `add-login` exists under `apps/nxt/openspec/changes/`
- **THEN** its change-list row displays `apps · nxt · add-login`

#### Scenario: Root-level change is unprefixed
- **WHEN** an active change `add-login` exists under the search root's `openspec/changes/`
- **THEN** its change-list row displays `add-login`

#### Scenario: Same folder name in two roots
- **WHEN** `openspec/changes/add-login` and `nxt/openspec/changes/add-login` are both active
- **THEN** the change list contains distinct rows for `add-login` and `nxt · add-login`

### Requirement: Change operations stay in the originating OpenSpec root
Selecting, opening, validating, and editing a change SHALL use that change's own OpenSpec project directory and artifacts. The displayed prefix SHALL NOT be passed as the OpenSpec change name to `openspec validate`.

#### Scenario: User validates a nested change
- **WHEN** the selected change is displayed as `nxt · add-login`
- **THEN** validation runs against the OpenSpec change `add-login` with the `nxt` OpenSpec project as its working directory

#### Scenario: User opens a nested artifact
- **WHEN** the user opens Proposal for `nxt · add-login`
- **THEN** the document viewer loads `nxt/openspec/changes/add-login/proposal.md`

### Requirement: Empty state reflects workspace-wide discovery
The sidebar SHALL report that no OpenSpec project exists only when discovery finds no OpenSpec roots under the search root. When at least one OpenSpec root exists but none has an active change, it SHALL report that there are no active changes.

#### Scenario: Workspace has no OpenSpec directories
- **WHEN** the search root and the two directory levels below it contain no `openspec/` directory
- **THEN** the sidebar reports that no OpenSpec project exists

#### Scenario: OpenSpec roots exist without active changes
- **WHEN** discovery finds one or more OpenSpec roots and none contains an active change
- **THEN** the sidebar reports that there are no active changes
