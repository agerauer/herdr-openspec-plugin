## Purpose

Let reviewers switch among a change's proposal, design, tasks, and specifications from inside the document viewer without returning to the artifact list.

## ADDED Requirements

### Requirement: Document viewer shows artifact tabs
While a document is open, the viewer SHALL display tabs for Proposal, Design, Tasks, and every specification in deterministic path order. The tab for the open artifact SHALL be visually distinguished and SHALL remain visible even when later tabs are clipped.

#### Scenario: Core document is open
- **WHEN** the user opens Proposal, Design, or Tasks
- **THEN** the viewer displays Proposal, Design, Tasks, and a tab for each specification, and marks the matching core tab as selected

#### Scenario: Specification is open
- **WHEN** the user opens a specification document
- **THEN** that specification's tab is visible and marked as selected

### Requirement: Tabs switch the open document
Left-clicking a visible tab SHALL select that artifact and open it when the document exists, or report that it does not exist yet when it is missing.

#### Scenario: User clicks an existing core tab
- **WHEN** a document is open and the user left-clicks the Design tab whose document exists
- **THEN** Design becomes selected and opens in the document viewer

#### Scenario: User clicks a missing core tab
- **WHEN** a document is open and the user left-clicks the Design tab whose document does not exist
- **THEN** Design becomes selected, the current document remains open, and the sidebar reports that the artifact does not exist yet

#### Scenario: User clicks a specification tab
- **WHEN** Proposal is open and the user left-clicks a specification tab whose document exists
- **THEN** that specification becomes selected and opens

#### Scenario: User clicks the open specification tab
- **WHEN** a specification is open and the user left-clicks that specification's tab
- **THEN** the open specification remains the current document

### Requirement: Narrow panes clip tabs without creating targets
Tabs that are not rendered because the pane is too narrow SHALL have no clickable region. Complete visible tabs SHALL remain clickable.

#### Scenario: Pane cannot fit every tab
- **WHEN** the viewer header cannot display every tab label
- **THEN** only the fully visible tabs have mouse targets

#### Scenario: Clipped tab is clicked
- **WHEN** the user clicks the region where a clipped tab would have appeared
- **THEN** the open document and current offset remain unchanged

### Requirement: Arrow keys move through viewer documents
While a document is open, Left SHALL open the previous existing document in Proposal, Design, Tasks, then specification order, and SHALL close the viewer when the open document is already the first existing document. Right SHALL open the next existing document in that order and SHALL leave the current document open when there is no later document, including when the last specification is open.

#### Scenario: User presses left from Proposal
- **WHEN** Proposal is open and the user presses Left
- **THEN** the document viewer closes and the selected change remains available in the main view

#### Scenario: User presses right from Proposal
- **WHEN** Proposal is open, Design exists, and the user presses Right
- **THEN** Design becomes selected and opens in the document viewer

#### Scenario: User presses right on a specification
- **WHEN** a specification is open, a later specification exists, and the user presses Right
- **THEN** the next specification in deterministic path order becomes selected and opens

#### Scenario: User presses right on the last specification
- **WHEN** the last specification is open and the user presses Right
- **THEN** the open specification remains the current document
