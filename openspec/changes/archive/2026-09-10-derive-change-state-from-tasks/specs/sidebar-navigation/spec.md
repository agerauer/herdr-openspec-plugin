## MODIFIED Requirements

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
