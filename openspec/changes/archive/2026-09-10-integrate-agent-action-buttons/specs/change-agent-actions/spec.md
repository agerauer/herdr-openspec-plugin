## Purpose

Lets a reviewer act on a change without leaving the sidebar by offering its single next action inline and submitting that action to the coding agent running in the neighbouring Herdr pane.

## ADDED Requirements

### Requirement: Each change offers a single derived next action

The sidebar SHALL derive at most one next action for every active change from that change's displayed state, using this mapping: `READY` maps to **apply**, `IN PROGRESS` maps to **investigate**, `DONE` maps to **archive**, and `DRAFT` and `INVALID` map to no action. The sidebar SHALL never offer more than one action for a change at a time.

#### Scenario: Ready change offers apply

- **WHEN** an active change's state is `READY`
- **THEN** its derived next action is **apply**

#### Scenario: In-progress change offers investigate

- **WHEN** an active change's state is `IN PROGRESS`
- **THEN** its derived next action is **investigate**

#### Scenario: Done change offers archive

- **WHEN** an active change's state is `DONE`
- **THEN** its derived next action is **archive**

#### Scenario: Draft or invalid change offers no action

- **WHEN** an active change's state is `DRAFT` or `INVALID`
- **THEN** it has no derived next action

### Requirement: The next action is shown as a button on the card status line inside Herdr

When the sidebar is running inside Herdr, it SHALL render a change's derived next action as a labelled button at the end of that change's card status line, labelled by the action (`apply`, `investigate`, or `archive`), without displacing or truncating the state and task-progress portion of the status line. A change with no derived next action SHALL show no button. When the sidebar is not running inside Herdr, it SHALL show no action button for any change and SHALL leave the card status line otherwise unchanged.

#### Scenario: Button appears for an actionable change under Herdr

- **WHEN** the sidebar runs inside Herdr and a change's derived next action is **apply**
- **THEN** its card status line ends with an `apply` button

#### Scenario: Done change shows an archive button labelled "archive"

- **WHEN** the sidebar runs inside Herdr and a change's state is `DONE`
- **THEN** its card status line ends with a button labelled `archive`

#### Scenario: No button for a non-actionable change

- **WHEN** the sidebar runs inside Herdr and a change's state is `DRAFT`
- **THEN** its card status line shows no action button

#### Scenario: No button outside Herdr

- **WHEN** the sidebar is not running inside Herdr
- **THEN** no change's card status line shows an action button, regardless of state

### Requirement: Triggering an action submits it to the neighbouring coding agent

The sidebar SHALL let the reviewer trigger a change's next action by clicking its button or, for the selected change, by a keyboard shortcut. Triggering the action SHALL submit a corresponding instruction to the coding agent in the pane immediately to the sidebar's left: **apply** submits the change's `/opsx:apply` command, **archive** submits the change's `/opsx:archive` command, and **investigate** submits a plain-language prompt naming the change and its task progress that asks the agent to examine the change's open tasks. Clicking a change's button SHALL also make that change the selected change.

#### Scenario: Apply submits the apply command

- **WHEN** the reviewer triggers the **apply** action for a change
- **THEN** the sidebar submits that change's `/opsx:apply` command to the agent in the pane to its left

#### Scenario: Archive submits the archive command

- **WHEN** the reviewer triggers the **archive** action for a change
- **THEN** the sidebar submits that change's `/opsx:archive` command to the agent in the pane to its left

#### Scenario: Investigate submits an investigation prompt

- **WHEN** the reviewer triggers the **investigate** action for a change
- **THEN** the sidebar submits a plain-language prompt that names the change and its task progress and asks the agent to look at the change's open tasks

#### Scenario: Clicking a button selects the change

- **WHEN** the reviewer clicks the action button on a change that is not currently selected
- **THEN** that change becomes the selected change and its action is triggered

### Requirement: An unavailable target is reported instead of failing silently

When the reviewer triggers an action but the action cannot be delivered — there is no pane to the sidebar's left, the neighbouring pane is not a coding agent, or that agent is currently blocked waiting on input — the sidebar SHALL leave the neighbouring pane unchanged and SHALL show the reviewer a short message explaining why nothing was sent. After a successful submission, the sidebar SHALL surface a confirmation and focus the neighbouring agent so the reviewer can watch and respond to it.

#### Scenario: No agent pane to the left

- **WHEN** the reviewer triggers an action and there is no coding-agent pane immediately to the sidebar's left
- **THEN** nothing is submitted and the sidebar shows a message that there is no agent to send to

#### Scenario: Neighbouring agent is blocked

- **WHEN** the reviewer triggers an action and the neighbouring agent is blocked waiting on input
- **THEN** nothing is submitted and the sidebar shows a message that the agent is busy

#### Scenario: Successful submission confirms and focuses the agent

- **WHEN** the reviewer triggers an action and the submission is accepted
- **THEN** the sidebar shows a confirmation and focuses the neighbouring agent pane
