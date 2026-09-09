## MODIFIED Requirements

### Requirement: Viewer header provides mouse back navigation
The document viewer SHALL expose its visible top back affordance as a mouse target that performs the same back action as the viewer's keyboard and footer controls. Visible artifact tabs in that header SHALL remain independent mouse targets and SHALL NOT be treated as empty header space.

#### Scenario: User clicks the viewer header back affordance
- **WHEN** the user left-clicks the visible back affordance at the top of an open document
- **THEN** the document viewer closes and the selected change and artifact remain available in the main view

#### Scenario: User clicks outside the viewer header target
- **WHEN** the user clicks elsewhere in the viewer header where no mouse action is displayed, including no back affordance and no artifact tab
- **THEN** the open document and current offset remain unchanged

### Requirement: Core artifacts have direct keyboard shortcuts
The sidebar SHALL use `p`, `d`, and `t` to open Proposal, Design, and Tasks, and `s` to open or cycle specifications, for the selected change. These shortcuts SHALL work while the change list has focus and while a document is open. Pressing `s` from the change list SHALL open the first specification in deterministic path order. Pressing `s` in the document viewer SHALL advance to the next specification and wrap to the first after the last.

#### Scenario: User opens an existing core artifact directly
- **WHEN** the change list has focus and the user presses the shortcut for an existing Proposal, Design, or Tasks artifact
- **THEN** the corresponding artifact becomes selected and opens in the document viewer

#### Scenario: User targets a missing core artifact directly
- **WHEN** the change list has focus and the user presses the shortcut for a missing Proposal, Design, or Tasks artifact
- **THEN** the corresponding artifact becomes selected and the sidebar reports that it does not exist yet

#### Scenario: User switches artifacts from the document viewer
- **WHEN** a document is open and the user presses `p`, `d`, or `t` for an existing Proposal, Design, or Tasks artifact
- **THEN** the corresponding artifact becomes selected and replaces the open document

#### Scenario: User opens the first specification from the change list
- **WHEN** the change list has focus, at least one specification exists, and the user presses `s`
- **THEN** the first specification in deterministic path order becomes selected and opens in the document viewer

#### Scenario: User cycles specifications in the document viewer
- **WHEN** a specification is open, more than one specification exists, and the user presses `s`
- **THEN** the next specification in deterministic path order becomes selected and opens, wrapping from the last specification to the first

#### Scenario: User presses s with a single specification
- **WHEN** a specification is open, it is the only specification, and the user presses `s`
- **THEN** that specification remains the open document

#### Scenario: User presses s with no specification documents
- **WHEN** the selected change has no specification document and the user presses `s`
- **THEN** the sidebar reports that the artifact does not exist yet and does not replace an already open document

#### Scenario: Direct shortcut is pressed outside the change list
- **WHEN** the artifact list has focus, no document is open, and the user presses `p`, `d`, `t`, or `s`
- **THEN** the sidebar does not replace the current artifact selection or open a different document through the direct shortcut
