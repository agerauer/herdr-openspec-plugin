## Purpose

Make task completion for every active OpenSpec change visible while scanning the sidebar's primary change list.

## ADDED Requirements

### Requirement: Each change row displays task progress
The sidebar SHALL display the number of completed checklist tasks and the total number of checklist tasks for every active change directly in that change's list row, formatted as `X/Y`.

#### Scenario: Change has completed and incomplete tasks
- **WHEN** an active change contains three completed checklist tasks and two incomplete checklist tasks
- **THEN** its change-list row displays `3/5`

#### Scenario: Change has no checklist tasks
- **WHEN** an active change has no checklist tasks, including when `tasks.md` does not yet exist
- **THEN** its change-list row displays `0/0`

### Requirement: Task progress remains legible in constrained widths
The sidebar SHALL reserve space for the complete `X/Y` value and shorten the displayed change name when necessary so the name and task progress do not overlap.

#### Scenario: Change name exceeds available row width
- **WHEN** a change name and its task progress cannot both fit in the available row width
- **THEN** the sidebar truncates the displayed name while retaining the complete task progress value

### Requirement: Selection applies to the complete change row
The sidebar SHALL preserve the visual association between a selected change and its displayed task progress.

#### Scenario: User selects a change
- **WHEN** a change row is selected in the change list
- **THEN** the selection treatment includes both the displayed change name and its task progress value
