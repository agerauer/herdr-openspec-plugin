## ADDED Requirements

### Requirement: Core artifacts precede specifications
The sidebar SHALL order each change's artifact rows as Proposal, Design, Tasks, and then every specification in deterministic path order. A missing core artifact or specification placeholder SHALL retain its position in that sequence.

#### Scenario: Change has multiple specifications
- **WHEN** a change has Proposal, Design, Tasks, and more than one specification
- **THEN** the artifact list displays Proposal first, Design second, Tasks third, and all specifications afterward in deterministic path order

#### Scenario: Core artifact is missing
- **WHEN** Proposal, Design, or Tasks does not exist for the selected change
- **THEN** its missing-artifact row remains in the corresponding core position before specification rows

### Requirement: Artifact-list capacity adapts to pane height
The sidebar SHALL show the total number of navigable artifact rows in the `ARTIFACTS` heading and SHALL display more than four artifact rows whenever the pane has sufficient unused height after preserving required regions and the supported change-list capacity.

#### Scenario: Tall pane contains more than four artifacts
- **WHEN** a selected change has more than four artifacts and the pane can display additional rows without overlap
- **THEN** the artifact viewport displays more than four rows at once

#### Scenario: Pane cannot display every artifact
- **WHEN** the pane does not have enough height for every artifact row and all required sidebar regions
- **THEN** the sidebar displays the largest artifact window that fits and keeps the selected artifact visible

#### Scenario: Artifact heading is rendered
- **WHEN** the selected change has a navigable artifact list
- **THEN** the heading displays `ARTIFACTS (N)` where `N` equals the total number of artifact rows, including visible missing-artifact placeholders

### Requirement: Main-view focus returns predictably to changes
The sidebar SHALL return focus from the artifact list to the change list when the user presses Escape in the main view, including immediately after Enter moved focus from the selected change to its artifacts.

#### Scenario: Escape follows Enter from a change
- **WHEN** the change list has focus, the user presses Enter, and then presses Escape without opening a document
- **THEN** focus returns from the artifact list to the selected change row

#### Scenario: Escape is pressed while changes already have focus
- **WHEN** the change list already has focus and the user presses Escape in the main view
- **THEN** the selected change and main view remain unchanged

### Requirement: Viewer header provides mouse back navigation
The document viewer SHALL expose its visible top back affordance as a mouse target that performs the same back action as the viewer's keyboard and footer controls.

#### Scenario: User clicks the viewer header back affordance
- **WHEN** the user left-clicks the visible back affordance at the top of an open document
- **THEN** the document viewer closes and the selected change and artifact remain available in the main view

#### Scenario: User clicks outside the viewer header target
- **WHEN** the user clicks elsewhere in the viewer header where no mouse action is displayed
- **THEN** the open document and current offset remain unchanged

### Requirement: Core artifacts have direct keyboard shortcuts
While the change list has focus in the main view, the sidebar SHALL use `p`, `d`, and `t` to open Proposal, Design, and Tasks, respectively, for the selected change.

#### Scenario: User opens an existing core artifact directly
- **WHEN** the change list has focus and the user presses the shortcut for an existing Proposal, Design, or Tasks artifact
- **THEN** the corresponding artifact becomes selected and opens in the document viewer

#### Scenario: User targets a missing core artifact directly
- **WHEN** the change list has focus and the user presses the shortcut for a missing Proposal, Design, or Tasks artifact
- **THEN** the corresponding artifact becomes selected and the sidebar reports that it does not exist yet

#### Scenario: Direct shortcut is pressed outside the change list
- **WHEN** the artifact list or document viewer has focus and the user presses `p`, `d`, or `t`
- **THEN** the sidebar does not replace the current artifact selection or open a different document through the direct shortcut

### Requirement: Edit action prefers Visual Studio Code
The document viewer's edit action SHALL open the current artifact with the `code` executable when that executable is available on `PATH`, and SHALL otherwise open it with `vi`.

#### Scenario: Visual Studio Code command is available
- **WHEN** the user invokes edit for an open artifact and `code` is available on `PATH`
- **THEN** the sidebar launches `code` with that artifact's path

#### Scenario: Visual Studio Code command is unavailable
- **WHEN** the user invokes edit for an open artifact and `code` is not available on `PATH`
- **THEN** the sidebar launches `vi` with that artifact's path

## MODIFIED Requirements

### Requirement: Document scrolling distinguishes lines from pages
The document viewer SHALL reliably scroll in both directions by one wrapped visual line for each Up/Down keypress and each recognized mouse-wheel step, while Page Up/Page Down SHALL scroll by one visible document page.

#### Scenario: User presses an arrow key in a document
- **WHEN** the user presses Up or Down while reading an open artifact
- **THEN** the document offset moves by one wrapped visual line in the corresponding direction

#### Scenario: User turns the mouse wheel in a document
- **WHEN** the document viewer receives one upward or downward mouse-wheel event
- **THEN** the document offset moves by one wrapped visual line in the corresponding direction

#### Scenario: User scrolls downward with the mouse wheel
- **WHEN** the terminal reports any supported encoding of one downward mouse-wheel step while a document is open
- **THEN** the document offset increases by one wrapped visual line unless already at the lower boundary

#### Scenario: User presses a page navigation key
- **WHEN** the user presses Page Up or Page Down while reading an open artifact
- **THEN** the document offset moves by one visible document page in the corresponding direction

#### Scenario: Scroll reaches a document boundary
- **WHEN** a line or page scroll would move before the first line or beyond the last available offset
- **THEN** the document offset is clamped to the valid document range
