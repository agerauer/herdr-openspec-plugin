## MODIFIED Requirements

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
