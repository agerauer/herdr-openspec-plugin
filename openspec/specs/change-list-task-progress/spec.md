# Change List Task Progress Specification

## Purpose

Make task completion for every active OpenSpec change visible while scanning the sidebar's primary change list.

## Requirements

### Requirement: Each change row displays task progress
The sidebar SHALL display the number of completed checklist tasks and the total number of checklist tasks for every active change on that change's card status line, formatted as `X/Y` alongside the change's status and artifact count.

#### Scenario: Change has completed and incomplete tasks
- **WHEN** an active change contains three completed checklist tasks and two incomplete checklist tasks
- **THEN** its card status line displays `3/5`

#### Scenario: Change has no checklist tasks
- **WHEN** an active change has no checklist tasks, including when `tasks.md` does not yet exist
- **THEN** its card status line displays `0/0`

### Requirement: Task progress remains legible in constrained widths
The sidebar SHALL reserve space for the complete `X/Y` value on the card status line and SHALL shorten other status-line content before the task progress, so the complete `X/Y` value remains visible when the status line cannot fit at full width. A change name too wide for the card SHALL be truncated on its own line without affecting the task progress value.

#### Scenario: Change name exceeds available row width
- **WHEN** a change name is wider than the card can display
- **THEN** the sidebar truncates the displayed name on the name line while the task progress value on the status line is unaffected

#### Scenario: Status line exceeds available card width
- **WHEN** a change's status, artifact count, and task progress cannot all fit on the card status line
- **THEN** the sidebar shortens the other status-line content while retaining the complete task progress value

### Requirement: Selection applies to the complete change row
The sidebar SHALL preserve the visual association between a selected change and its displayed task progress across the whole change card.

#### Scenario: User selects a change
- **WHEN** a change card is selected in the change list
- **THEN** the selection treatment includes the change name and its card status line, including the displayed task progress value

### Requirement: Change state is derived from task completion and validity

The sidebar SHALL derive a single state for each active change from its task completion and its openspec validity, using these rules in order: a change whose validation failed SHALL be **INVALID**; otherwise a change with no checklist tasks (`0/0`) or that is an openspec draft (a required artifact is missing) SHALL be **DRAFT**; otherwise a change with tasks but none complete (`0/Y`) SHALL be **READY**; otherwise a change with some but not all tasks complete (`X/Y`) SHALL be **IN PROGRESS**; otherwise a change with every task complete (`Y/Y`) SHALL be **DONE**. This derived state SHALL be the single state shown for the change; the raw openspec status SHALL NOT be shown as a separate token.

#### Scenario: Valid change with no tasks is draft

- **WHEN** a change is valid, has all required artifacts, and has `0/0` tasks
- **THEN** its derived state is DRAFT

#### Scenario: Openspec draft is draft regardless of task counts

- **WHEN** a change is missing a required artifact (an openspec draft) and has some tasks complete
- **THEN** its derived state is DRAFT

#### Scenario: Valid change with no tasks done is ready

- **WHEN** a change is valid and has tasks with none complete (`0/Y`)
- **THEN** its derived state is READY

#### Scenario: Valid change partway through is in progress

- **WHEN** a change is valid and has some but not all tasks complete (`X/Y`)
- **THEN** its derived state is IN PROGRESS

#### Scenario: Valid change with all tasks done is done

- **WHEN** a change is valid and has every task complete (`Y/Y`)
- **THEN** its derived state is DONE

#### Scenario: Failed validation overrides to invalid

- **WHEN** a change's validation failed
- **THEN** its derived state is INVALID regardless of its task counts
