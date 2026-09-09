## MODIFIED Requirements

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
