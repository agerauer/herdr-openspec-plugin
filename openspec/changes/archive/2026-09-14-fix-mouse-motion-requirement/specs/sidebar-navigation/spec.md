## MODIFIED Requirements

### Requirement: Mouse capture can be toggled for terminal selection

The sidebar SHALL provide a key that suspends its own mouse handling and restores it when pressed again, and SHALL advertise this toggle in the footer. While mouse handling is suspended, the terminal's native text selection and copy work over the pane and the sidebar's own mouse actions (row/tab/footer clicks and wheel scrolling) are inactive. While mouse handling is active, those mouse actions work as before, and the sidebar SHALL request the mouse event types its terminal needs in order to recognise a wheel step in both directions — including mouse-motion reporting on platforms whose terminal library has no button-5 encoding and reports a downward step with the motion bit.

#### Scenario: User suspends mouse handling to copy text

- **WHEN** the user presses the mouse-toggle key
- **THEN** the sidebar stops capturing the mouse so the terminal can select and copy text over the pane, and the footer reflects that mouse handling is suspended

#### Scenario: User restores mouse handling

- **WHEN** mouse handling is suspended and the user presses the mouse-toggle key again
- **THEN** in-pane clicks and wheel scrolling work again

#### Scenario: Toggle is advertised in the footer

- **WHEN** the main view or the document viewer is shown
- **THEN** the footer includes a hint for the mouse-capture toggle

#### Scenario: Downward wheel step on a platform with no button-5 encoding

- **WHEN** mouse handling is active and the terminal reports a downward wheel step using the motion bit, because its terminal library provides no button-5 encoding
- **THEN** the sidebar has requested that event type, so the step is decoded rather than discarded, and the document scrolls down
