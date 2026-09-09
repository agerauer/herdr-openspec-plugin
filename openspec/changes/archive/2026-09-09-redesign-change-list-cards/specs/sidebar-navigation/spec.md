## ADDED Requirements

### Requirement: Change rows render as inline cards

The sidebar SHALL render every active change as a multi-line card in the change list. Each card SHALL show, on successive lines: a selection marker followed by the change name in bold; a status line combining the change's status, its artifact count, and its task progress separated by a middle dot as `STATUS · N Artifacts · done/total`; and the change's description. A blank line SHALL separate adjacent cards. The card SHALL be shown for every change, not only the selected one, and the selected change's card SHALL carry the selection marker with its name emphasized. Left-clicking any line of a card SHALL select that change and give the change list focus; clicking where no card is shown SHALL leave the selection unchanged. Pressing Enter on the selected change SHALL open its Proposal in the document viewer when it exists, or report that it does not exist yet.

#### Scenario: Change card shows status, counts, and description

- **WHEN** a change with status READY, four artifacts, and sixteen tasks with none done is displayed
- **THEN** its card shows the change name in bold, a status line reading `READY · 4 Artifacts · 0/16`, and its description on the following line

#### Scenario: Every change shows a full card

- **WHEN** several active changes exist
- **THEN** each change is shown as its own card with name, status line, and description, whether or not it is selected

#### Scenario: User clicks a change card

- **WHEN** the user left-clicks any line of a visible change card
- **THEN** that change becomes selected and the change list receives focus

#### Scenario: User clicks empty space

- **WHEN** the user clicks an area of the change list where no card is shown
- **THEN** the selected change and view remain unchanged

#### Scenario: User opens the selected change

- **WHEN** the change list has focus and the user presses Enter on the selected change whose Proposal exists
- **THEN** the change's Proposal opens in the document viewer

### Requirement: Worktree-touched changes are indicated by color

The sidebar SHALL indicate worktree-touched changes with color on the change name rather than a glyph marker and SHALL NOT display a separate touched-change icon. Touched changes SHALL remain grouped ahead of untouched changes.

#### Scenario: Touched change is shown

- **WHEN** a change is worktree-touched
- **THEN** its card name is shown in the touched-change color and no icon precedes the name

#### Scenario: Untouched change is shown

- **WHEN** a change is not worktree-touched
- **THEN** its card name is shown in the default color and no icon precedes the name

### Requirement: The main footer lists the available shortcuts

The change-list footer SHALL present the main view's shortcuts — movement, open, the artifact-document keys, edit, validate, refresh, and close — so they are discoverable at a glance, and hints that do not fit the pane width on one row SHALL wrap onto further rows rather than be dropped. The open, document-keys, edit, validate, refresh, and close hints SHALL be clickable and perform their action; clicking the document-keys hint SHALL open the selected change's Proposal. The movement hint MAY be shown as a display-only legend without a click target.

#### Scenario: Footer lists the main shortcuts

- **WHEN** the change list is shown
- **THEN** the footer displays hints for movement, open, the document keys, edit, validate, refresh, and close, wrapping onto additional rows when the pane is too narrow to show them on one

#### Scenario: Clicking the document-keys hint opens the Proposal

- **WHEN** the user clicks the document-keys footer hint on the change list
- **THEN** the selected change's Proposal opens in the document viewer

#### Scenario: Single-action footer hints stay clickable

- **WHEN** the change-list footer displays the open, edit, validate, refresh, and close hints
- **THEN** each of those hints is clickable and performs the same action as its keyboard shortcut

## MODIFIED Requirements

### Requirement: Change-list capacity adapts to pane height
The sidebar SHALL display as many whole active change cards as the pane height fits, with no fixed upper limit, and SHALL reduce the count only as needed to keep the message and footer rows usable without overlap. Because each change is a multi-line card, fewer changes fit a given height than single-line rows did. At least one card SHALL be shown whenever any room remains.

#### Scenario: Tall pane contains at least 15 changes
- **WHEN** the pane has vertical space for at least 15 change cards plus the message and footer rows and at least 15 active changes exist
- **THEN** the change list displays at least 15 change cards at once

#### Scenario: Pane cannot fit 15 changes and the remaining regions
- **WHEN** the pane does not have room for every change card plus the message and footer rows
- **THEN** the sidebar displays the largest number of whole change cards that fits the available height

#### Scenario: Pane has room for more than 15 cards
- **WHEN** the pane is tall enough for more than 15 change cards and more than 15 active changes exist
- **THEN** the change list displays more than 15 change cards, limited only by the available height

#### Scenario: Selection moves beyond the visible change window
- **WHEN** keyboard or mouse navigation selects a change outside the current visible window
- **THEN** the change-list window adjusts so the selected change's card remains visible

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
- **WHEN** a document is open and the user presses `p`, `d`, `t`, or `s`
- **THEN** the shortcut switches the open document as specified above without requiring a return to the change list first

### Requirement: Edit action prefers Visual Studio Code
The document viewer's edit action SHALL open the current artifact with the `code` executable when it is available on `PATH`, and SHALL otherwise open it with `vi`. From the change list, the edit action SHALL open the selected change's folder with the `code` executable when it is available on `PATH`, and SHALL report that opening the folder is unavailable when `code` is not on `PATH`.

#### Scenario: Visual Studio Code command is available
- **WHEN** the user invokes edit for an open artifact and `code` is available on `PATH`
- **THEN** the sidebar launches `code` with that artifact's path

#### Scenario: Visual Studio Code command is unavailable
- **WHEN** the user invokes edit for an open artifact and `code` is not available on `PATH`
- **THEN** the sidebar launches `vi` with that artifact's path

#### Scenario: User opens a change folder from the change list
- **WHEN** the change list is focused, no document is open, and the user invokes edit while `code` is available on `PATH`
- **THEN** the sidebar launches `code` with the selected change's folder path

#### Scenario: Change-folder edit without Visual Studio Code
- **WHEN** the change list is focused, no document is open, and the user invokes edit while `code` is not available on `PATH`
- **THEN** the sidebar reports that opening the folder is unavailable and does not launch `vi`

## REMOVED Requirements

### Requirement: Change and artifact rows support mouse activation
**Reason**: The main view no longer shows an artifact list, and change rows became multi-line cards. Change-card mouse activation is now specified by "Change rows render as inline cards"; artifact activation happens through the document viewer's tabs.
**Migration**: Click a change card to select it (see "Change rows render as inline cards"); open and switch artifacts via the viewer tabs (`document-viewer-tabs`) or the `p`/`d`/`t`/`s` shortcuts.

### Requirement: Core artifacts precede specifications
**Reason**: This requirement ordered the main view's artifact rows, which no longer exist.
**Migration**: Artifact order (Proposal, Design, Tasks, then specifications in deterministic path order) is specified for the document viewer by `document-viewer-tabs`.

### Requirement: Artifact-list capacity adapts to pane height
**Reason**: The main view no longer shows an always-visible artifact list, so there is no artifact viewport to size or `ARTIFACTS (N)` heading to render.
**Migration**: The artifact count is shown on each change card's status line; artifacts are opened with `p`/`d`/`t`/`s` or Enter and browsed via the viewer tabs (`document-viewer-tabs`).

### Requirement: Main-view focus returns predictably to changes
**Reason**: There is no artifact-list focus in the main view to return from; the change list is the only main-view focus.
**Migration**: Escape from an open document returns to the main view with the selected change intact, as specified by the document viewer.
