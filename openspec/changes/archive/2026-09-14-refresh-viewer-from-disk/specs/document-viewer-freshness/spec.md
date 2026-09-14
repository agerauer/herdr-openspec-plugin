## Purpose

Keeps the open document in the review pane in sync with its file on disk, so a reviewer reading an artifact while an agent edits it sees the current contents rather than a stale copy.

## ADDED Requirements

### Requirement: Opening a document reads it from disk

When the sidebar opens a document in the viewer — through any navigation, including Enter, the `p`/`d`/`t`/`s` shortcuts, the arrow keys, and clicking a tab — it SHALL read that document's current file contents from disk and display them, rather than reusing text captured by an earlier change-list scan.

#### Scenario: Opening a document that changed since the last scan

- **WHEN** a document's file has changed on disk since the change list was last scanned, and the reviewer opens that document
- **THEN** the viewer displays the file's current contents

#### Scenario: Switching to a previously opened document that has since changed

- **WHEN** the reviewer switches (by tab, shortcut, or arrow) to a document that was opened earlier and whose file has since changed on disk
- **THEN** the viewer displays the file's current contents

### Requirement: A visible document refreshes when its file changes

While a document is open, the sidebar SHALL detect changes to that document's underlying file and re-read it so the displayed contents reflect the file, without the reviewer pressing a key or otherwise acting, and without depending on the change-list scan. The reviewer's scroll position SHALL be preserved and clamped to the refreshed document's length.

#### Scenario: The file changes while the reviewer is reading it

- **WHEN** a document is open and visible and its underlying file changes on disk
- **THEN** the viewer updates to show the file's current contents on its own

#### Scenario: Scroll position is kept across a refresh

- **WHEN** an open document is refreshed because its file changed and the reviewer had scrolled into the document
- **THEN** the scroll position is preserved, clamped to the refreshed document's length so it never rests beyond the last line

#### Scenario: An unchanged file is not reprocessed

- **WHEN** a document is open and its underlying file has not changed
- **THEN** the viewer does not re-read the file

### Requirement: A removed or unreadable open document degrades gracefully

When the file for the open document is removed or becomes unreadable while it is open, the sidebar SHALL show the document as empty rather than displaying stale contents or failing.

#### Scenario: The open document's file is deleted

- **WHEN** a document is open and its underlying file is removed
- **THEN** the viewer shows the document as empty and the pane keeps running
