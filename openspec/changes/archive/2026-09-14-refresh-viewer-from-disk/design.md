## Context

The viewer renders `self.viewer.content`, a string on an in-memory `Artifact`. Those artifacts are built by `discover_project_changes`, which reads every file with `read_artifact(path)`, and are only rebuilt by `reload()`. `reload()` runs on the `r` key and on a ~2s timer in `run()`, and early-returns unless a fingerprint of all mtimes/sizes under `openspec/changes/` has changed. Navigation (`open_selected_artifact`, `open_or_cycle_specification`, `select_viewer_tab`, `move_viewer_tab`) only points `self.viewer` at an already-loaded artifact; it never touches disk. `render_viewer(content, width)` caches its styled lines keyed on `content`, and `draw_viewer` clamps `viewer_offset` to the rendered length every frame.

So the open document's freshness is bound entirely to the coarse whole-tree poll, and navigation reflects only the last poll — confirmed by a repro where an edit made after the last scan was invisible until the next fingerprint change.

## Goals / Non-Goals

**Goals:**
- The open document reflects its file on disk on navigation and while visible, independent of the change-tree poll.
- Cheap enough to run every frame; preserve scroll; survive a deleted file.

**Non-Goals:**
- Refreshing the change list faster (state, `done/total`, ordering stay on the existing poll).
- A filesystem watcher or new dependency — a per-frame `stat` is enough at this scale.
- Recomputing task counts/goal from a viewer re-read (those belong to the list's reload).

## Decisions

### One choke point: refresh the open document before rendering, keyed on path + mtime
Add a `refresh_open_document()` called at the top of `draw_viewer` (before `render_viewer`). It tracks a signature — `(path, st_mtime_ns)` — of the bytes currently loaded into the viewer. Each frame:
- if there is no open document, or it has no file path (the synthetic `specs` placeholder), do nothing;
- otherwise `stat` the file; if the signature differs from the tracked one (different path, or changed/gone mtime), re-read via `read_artifact(self.viewer.path)` into `self.viewer.content` and store the new signature.

This single mechanism delivers **both** spec requirements:
- *Navigation* changes `self.viewer` (and its path), so the first frame after opening re-reads — "opening reads from disk."
- *While visible*, a changed mtime re-reads on the next frame — "refresh while visible."

To guarantee a fresh read on every navigation even in the rare same-mtime case, reset the tracked signature to `None` whenever `self.viewer` is assigned (a small `set_viewer`/reset used by the open paths), so a reopen always re-reads once.

- *Alternative — re-read explicitly in each navigation method AND separately poll while visible:* duplicates the disk read across four navigation call sites and a timer, and is easy to leave incomplete (e.g. arrow nav vs. `s` cycling). The draw-time choke point covers every path in one place. Rejected.
- *Alternative — a `watchdog`/kqueue file watcher:* new dependency and lifecycle for a single open file; a per-frame `stat` is simpler and sufficient.

### Cost and cache
`draw_viewer` runs at most a few times per second while idle (the `getch` timeout is 250ms) and more only while a key is held; one `stat` per frame is negligible, and the file is re-read **only** when the signature changes. Because `render_viewer` already keys its cache on `content`, a refreshed string invalidates the render automatically — no separate cache bust. `viewer_offset` is already clamped every frame, so a shorter refreshed document simply clamps into range.

### Deletion and unreadable files
`read_artifact` already returns `""` when the path is missing or not a file, so a delete-while-open naturally yields an empty document instead of stale text or an exception; the `stat` is wrapped so a missing file is treated as "changed" and triggers the empty re-read.

## Risks / Trade-offs

- **Reading a file mid-write (partial content flicker)** → the next frame re-reads once the writer finishes; transient and self-correcting. Acceptable for a review pane.
- **mtime granularity** → `st_mtime_ns` is nanosecond on the target filesystems; a same-instant rewrite is additionally covered by resetting the signature on navigation.
- **Scope divergence between viewer and list** → for up to ~2s the card's `done/total` can trail the open tasks.md the reviewer is watching refresh. Accepted; making the list live is a separate change.
