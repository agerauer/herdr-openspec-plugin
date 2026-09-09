## ADDED Requirements

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
