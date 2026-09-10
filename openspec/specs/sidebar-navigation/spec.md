# Sidebar Navigation Specification

## Purpose

Provide efficient, predictable keyboard and mouse navigation for active changes, their artifacts, and rendered OpenSpec documents in the Herdr sidebar.

## Requirements

### Requirement: Change rows render as inline cards

The sidebar SHALL render every active change as a multi-line card in the change list. Each card SHALL show, on successive lines: a selection marker followed by the change name in bold; a status line leading with the change's derived state (color-coded so it stands out — INVALID red, DRAFT dim, READY, IN PROGRESS, and DONE each in their own color), followed by the change's task progress and artifact count separated by a middle dot as `STATE · done/total · N Artifacts`; and the change's description. The raw openspec status SHALL NOT be shown as a separate token. A blank line SHALL separate adjacent cards. The card SHALL be shown for every change, not only the selected one, and the selected change's card SHALL carry the selection marker with its name emphasized. Left-clicking any line of a card SHALL select that change and give the change list focus; clicking where no card is shown SHALL leave the selection unchanged. Pressing Enter on the selected change SHALL open its Proposal in the document viewer when it exists, or report that it does not exist yet.

#### Scenario: Change card shows status, counts, and description

- **WHEN** a valid change with all required artifacts, four artifacts, and sixteen tasks with none done is displayed
- **THEN** its card shows the change name in bold, a status line reading `READY · 0/16 · 4 Artifacts` with the leading `READY` state color-coded and prominent, and its description on the following line

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
- **WHEN** a document is open and the user presses `p`, `d`, `t`, or `s`
- **THEN** the shortcut switches the open document as specified above without requiring a return to the change list first

### Requirement: Edit action prefers Visual Studio Code
The edit action SHALL open the selected change's folder with the `code` executable when it is available on `PATH`, from both the change list and the document viewer, and SHALL report that opening the folder is unavailable when `code` is not on `PATH`. The edit action SHALL NOT open an individual file or fall back to `vi`.

#### Scenario: Visual Studio Code command is available
- **WHEN** the user invokes edit and `code` is available on `PATH`
- **THEN** the sidebar launches `code` with the selected change's folder path

#### Scenario: Visual Studio Code command is unavailable
- **WHEN** the user invokes edit and `code` is not available on `PATH`
- **THEN** the sidebar reports that opening the folder is unavailable and does not launch `vi`

#### Scenario: User opens a change folder from the change list
- **WHEN** the change list is focused and the user invokes edit while `code` is available on `PATH`
- **THEN** the sidebar launches `code` with the selected change's folder path

#### Scenario: User opens the change folder from the document viewer
- **WHEN** a document is open and the user invokes edit while `code` is available on `PATH`
- **THEN** the sidebar launches `code` with the selected change's folder path rather than editing the open file

#### Scenario: Change-folder edit without Visual Studio Code
- **WHEN** the user invokes edit while `code` is not available on `PATH`
- **THEN** the sidebar reports that opening the folder is unavailable and does not launch `vi`

### Requirement: Escape leaves the document viewer without delay

Pressing Escape while a document is open SHALL return to the main view as promptly as the Left/back control does, without the multi-hundred-millisecond pause that an unshortened terminal escape-sequence timeout introduces.

#### Scenario: Escape returns from a document promptly

- **WHEN** a document is open and the user presses Escape
- **THEN** the viewer closes and returns to the main view without a perceptible delay, matching the responsiveness of leaving via Left

### Requirement: Mouse capture can be toggled for terminal selection

The sidebar SHALL provide a key that suspends its own mouse handling and restores it when pressed again, and SHALL advertise this toggle in the footer. While mouse handling is suspended, the terminal's native text selection and copy work over the pane and the sidebar's own mouse actions (row/tab/footer clicks and wheel scrolling) are inactive. While mouse handling is active, those mouse actions work as before. The sidebar SHALL NOT request mouse-motion reporting.

#### Scenario: User suspends mouse handling to copy text

- **WHEN** the user presses the mouse-toggle key
- **THEN** the sidebar stops capturing the mouse so the terminal can select and copy text over the pane, and the footer reflects that mouse handling is suspended

#### Scenario: User restores mouse handling

- **WHEN** mouse handling is suspended and the user presses the mouse-toggle key again
- **THEN** in-pane clicks and wheel scrolling work again

#### Scenario: Toggle is advertised in the footer

- **WHEN** the main view or the document viewer is shown
- **THEN** the footer includes a hint for the mouse-capture toggle

### Requirement: The review pane opens at about half the available width

When the sidebar first opens beside the invoking pane and the layout can be set, the pane SHALL be given about half the available width rather than a narrow fraction. Manual resizing afterward SHALL be preserved.

#### Scenario: Pane opens at half width

- **WHEN** the review pane is opened and the layout split can be set
- **THEN** the pane is allotted approximately half of the split's width

#### Scenario: Layout cannot be set

- **WHEN** the layout split cannot be determined or set
- **THEN** the pane still opens and the user can resize it manually
