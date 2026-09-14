## Why

The document viewer renders a copy of each artifact's text captured the last time the whole `openspec/changes/` tree was scanned. Opening or switching to a document never re-reads it, and a document already on screen only updates when the coarse ~2s change-tree fingerprint poll happens to fire. So while an agent rewrites a proposal or checks off tasks in the pane next door, the reviewer keeps seeing a stale document — the thing they are actively reading is the one thing that does not stay current.

## What Changes

- The open document SHALL reflect the file on disk: re-read it when the reviewer opens or switches to a document, and refresh it while it stays visible when the underlying file changes — with no keypress and no reliance on the change-tree poll.
- Refreshing preserves the reader's scroll position (clamped to the new length), and a file that is removed or becomes unreadable while open shows as empty instead of crashing or showing stale text.
- Scope is the **document viewer only**. The change-list cards (state, `done/total`, description, ordering) keep refreshing on the existing tree poll; this change does not touch that path.

## Capabilities

### New Capabilities
- `document-viewer-freshness`: the open document stays in sync with its file on disk — re-read on navigation and refreshed in place while visible.

### Modified Capabilities
<!-- None. Rendering (document-viewer-markdown), tabs/navigation (document-viewer-tabs),
     and scroll geometry (sidebar-navigation) are unchanged; this adds a new concern
     — when the open document's bytes are read — on top of them. -->

## Impact

- `sidebar.py`: refresh the open document's content from disk before rendering, keyed on the file's path and modification time (one `stat` per draw, re-read only on change); reset the tracking when the open document changes. No change to the change-list reload/fingerprint path.
- `tests/test_sidebar.py`: unit tests for the re-read decision and for the observable refresh on navigation, on a mid-view edit (offset preserved), and on deletion.
- `README.md`: note that an open document tracks its file live.
- No new dependencies; no change to how the change list scans.
