## ADDED Requirements

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
