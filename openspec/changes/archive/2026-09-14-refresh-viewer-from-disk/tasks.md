## 1. Re-read decision

- [x] 1.1 Add a pure helper that decides whether the open document must be re-read — given the tracked signature and the current file signature `(path, mtime)` (with a missing file represented distinctly) — returning true when they differ. Unit-test: same signature → false; changed mtime → true; missing file → true; different path → true.

## 2. Refresh the open document before rendering

- [x] 2.1 Add `refresh_open_document()` that, when a document with a file path is open, stats the file, and on a signature change re-reads it via `read_artifact` into `self.viewer.content` and stores the new signature; no-op when the viewer is closed or has no path (the synthetic `specs` placeholder). Wrap the `stat` so a missing file is treated as changed and yields empty content. Call it at the top of `draw_viewer`, before `render_viewer`. Initialize the tracking field in `__init__` and the test harness.
- [x] 2.2 Reset the tracked signature whenever `self.viewer` is assigned during navigation, so opening or switching to a document always re-reads once on the next frame. Verify every open path resets it (Enter/open, `p`/`d`/`t`, `s` cycling, arrow tab moves, tab click).

## 3. Tests for observable behavior

- [x] 3.1 Navigation re-read: build a sidebar over a temp change, open a document, edit its file on disk, re-open/switch to it, draw, and assert the viewer shows the new contents.
- [x] 3.2 Refresh while visible: with a document open and drawn once, edit its file, draw again, and assert the content updates with no input and that `viewer_offset` is preserved and clamped to the shorter refreshed document.
- [x] 3.3 Unchanged file: with a document open and drawn, draw again without changing the file and assert the file is not re-read (e.g. the re-read decision returns false / read count does not increase).
- [x] 3.4 Deletion: with a document open, remove its file, draw, and assert the viewer shows empty content and does not raise.

## 4. Docs and verification

- [x] 4.1 Update `README.md` to note that an open document tracks its file live (refreshes on open and while visible), distinct from the periodic change-list refresh.
- [x] 4.2 Run `python3 -m unittest discover -s tests -v` and confirm the whole suite passes; run `openspec validate refresh-viewer-from-disk --strict` and confirm it passes.
