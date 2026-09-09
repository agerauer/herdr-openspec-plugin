## Purpose

Provide efficient, predictable keyboard and mouse navigation for active changes, their artifacts, and rendered OpenSpec documents in the Herdr sidebar.

## ADDED Requirements

### Requirement: Change-list capacity adapts to pane height
The sidebar SHALL display up to 15 active change rows when the pane has sufficient height and SHALL reduce that number when necessary to keep selected-change information, artifact navigation, messages, and footer controls usable without overlap.

#### Scenario: Tall pane contains at least 15 changes
- **WHEN** the pane has enough vertical space for all required sidebar regions and at least 15 active changes exist
- **THEN** the change list displays 15 change rows at once

#### Scenario: Pane cannot fit 15 changes and the remaining regions
- **WHEN** displaying 15 change rows would overlap or displace required selected-change, artifact, message, or footer content
- **THEN** the sidebar displays the largest smaller number of change rows that fits the available height

#### Scenario: Selection moves beyond the visible change window
- **WHEN** keyboard or mouse navigation selects a change outside the current visible window
- **THEN** the change-list window adjusts so the selected change remains visible

### Requirement: Change and artifact rows support mouse activation
The sidebar SHALL provide mouse actions for every visible change row and artifact row.

#### Scenario: User clicks a visible change
- **WHEN** the user left-clicks a visible change row
- **THEN** that change becomes selected, change-list navigation receives focus, and its details and artifacts are displayed

#### Scenario: User clicks an existing artifact
- **WHEN** the user left-clicks a visible artifact row whose document exists
- **THEN** that artifact becomes selected and opens in the document viewer

#### Scenario: User clicks a missing artifact
- **WHEN** the user left-clicks a visible artifact row whose document does not exist
- **THEN** that artifact becomes selected and the sidebar reports that the artifact does not exist yet

#### Scenario: User clicks outside an interactive row
- **WHEN** the user clicks an area that has no visible mouse target
- **THEN** the sidebar leaves its current selection and view unchanged

### Requirement: Footer hints support equivalent mouse actions
Every visible action hint in the bottom footer SHALL be clickable and SHALL perform the same action as its displayed keyboard shortcut.

#### Scenario: User clicks a main-view footer action
- **WHEN** the user clicks the visible open, validate, or close hint in the main-view footer
- **THEN** the sidebar performs the same action as Enter, `v`, or `q`, respectively

#### Scenario: User clicks a viewer footer action
- **WHEN** the user clicks the visible back, edit, or close hint in the document-viewer footer
- **THEN** the sidebar performs the same action as Left/Escape, `e`, or `q`, respectively

#### Scenario: Footer hint is clipped by pane width
- **WHEN** a footer hint is not rendered because the pane is too narrow
- **THEN** the non-visible hint has no clickable region

### Requirement: Document scrolling distinguishes lines from pages
The document viewer SHALL scroll by one wrapped visual line for each Up/Down keypress and each mouse-wheel step, while Page Up/Page Down SHALL scroll by one visible document page.

#### Scenario: User presses an arrow key in a document
- **WHEN** the user presses Up or Down while reading an open artifact
- **THEN** the document offset moves by one wrapped visual line in the corresponding direction

#### Scenario: User turns the mouse wheel in a document
- **WHEN** the document viewer receives one upward or downward mouse-wheel event
- **THEN** the document offset moves by one wrapped visual line in the corresponding direction

#### Scenario: User presses a page navigation key
- **WHEN** the user presses Page Up or Page Down while reading an open artifact
- **THEN** the document offset moves by one visible document page in the corresponding direction

#### Scenario: Scroll reaches a document boundary
- **WHEN** a line or page scroll would move before the first line or beyond the last available offset
- **THEN** the document offset is clamped to the valid document range
