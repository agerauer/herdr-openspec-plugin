## ADDED Requirements

### Requirement: Tab bar color-codes artifact groups

The viewer tab bar SHALL render tabs in three visually distinct color groups — the standard artifacts (Proposal, Design, Tasks), the non-standard change documents, and the specifications — so a tab's kind is recognizable by color. The selected tab SHALL keep its selected emphasis regardless of group.

#### Scenario: Tabs of different kinds are shown

- **WHEN** a change has standard artifacts, at least one non-standard document, and at least one specification, and a document is open
- **THEN** the standard tabs, the non-standard tabs, and the specification tabs are each shown in their group's color, and the open document's tab keeps its selected emphasis

### Requirement: Tab bar wraps onto multiple rows

When the tabs do not fit the header on a single row, the viewer SHALL wrap them onto additional rows rather than dropping the overflow, and every tab that is drawn SHALL be a mouse target. A tab that cannot be drawn because the wrapped rows exceed the header's available height SHALL have no clickable region.

#### Scenario: Tabs exceed one row

- **WHEN** the change has more tabs than fit the header width on one row
- **THEN** the tabs wrap onto additional header rows and every drawn tab is clickable

#### Scenario: Wrapped rows exceed the available height

- **WHEN** the wrapped tab rows do not all fit the header's available height
- **THEN** a tab that is not drawn has no clickable region

### Requirement: Change name heads the document viewer

The viewer SHALL display the change's name above the tab bar, styled distinctly from the tabs so it reads as the document's heading rather than a tab.

#### Scenario: Open document shows the change heading

- **WHEN** a document is open
- **THEN** the change name appears on a row above the tab bar with a style different from the tabs

### Requirement: Document viewer footer advertises the artifact shortcuts

The document viewer's footer SHALL advertise the `p`/`d`/`t`/`s` document shortcuts alongside its back, edit, and close hints.

#### Scenario: Footer lists the document shortcuts

- **WHEN** a document is open
- **THEN** the viewer footer shows the `p`/`d`/`t`/`s` shortcut hint in addition to back, edit, and close

## MODIFIED Requirements

### Requirement: Document viewer shows artifact tabs
While a document is open, the viewer SHALL display tabs for Proposal, Design, and Tasks, then a tab for every other Markdown document in the change's folder (the non-standard artifacts, in deterministic order), then every specification in deterministic path order. The tab for the open artifact SHALL be visually distinguished and SHALL remain visible, with the tab bar wrapping rather than hiding later tabs.

#### Scenario: Core document is open
- **WHEN** the user opens Proposal, Design, or Tasks
- **THEN** the viewer displays Proposal, Design, and Tasks, then any non-standard document tabs, then a tab for each specification, and marks the matching core tab as selected

#### Scenario: Specification is open
- **WHEN** the user opens a specification document
- **THEN** that specification's tab is visible and marked as selected

#### Scenario: Non-standard document is open
- **WHEN** the change has a Markdown document in its folder other than proposal, design, or tasks and the user opens it
- **THEN** a tab for that document is shown after Tasks and before the specifications and is marked as selected

### Requirement: Arrow keys move through viewer documents
While a document is open, Left SHALL open the previous existing document in Proposal, Design, Tasks, then non-standard-artifact, then specification order, and SHALL close the viewer when the open document is already the first existing document. Right SHALL open the next existing document in that order and SHALL leave the current document open when there is no later document, including when the last specification is open.

#### Scenario: User presses left from Proposal
- **WHEN** Proposal is open and the user presses Left
- **THEN** the document viewer closes and the selected change remains available in the main view

#### Scenario: User presses right from Proposal
- **WHEN** Proposal is open, Design exists, and the user presses Right
- **THEN** Design becomes selected and opens in the document viewer

#### Scenario: User presses right past the standard artifacts
- **WHEN** Tasks is open, a non-standard document exists, and the user presses Right
- **THEN** the first non-standard document becomes selected and opens, before any specification

#### Scenario: User presses right on a specification
- **WHEN** a specification is open, a later specification exists, and the user presses Right
- **THEN** the next specification in deterministic path order becomes selected and opens

#### Scenario: User presses right on the last specification
- **WHEN** the last specification is open and the user presses Right
- **THEN** the open specification remains the current document

## REMOVED Requirements

### Requirement: Narrow panes clip tabs without creating targets
**Reason**: Tabs now wrap onto additional header rows instead of being clipped, so the "clip the overflow" behavior no longer applies.
**Migration**: See "Tab bar wraps onto multiple rows" — overflowing tabs wrap and stay clickable; only tabs that cannot be drawn because the wrapped rows exceed the header height have no target.
