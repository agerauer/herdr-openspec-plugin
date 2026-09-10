## Why

The prominent word on each change card is the openspec status (`READY`), which is both too loud and too coarse: nearly every change reads `READY` regardless of how much work is actually done. What a reviewer scanning the list wants to know is how far along a change is — and that is exactly what the task counts already encode.

## What Changes

- Derive a change's **state** from its task completion and validity, and show that as the prominent, color-coded word on the card status line, replacing the raw openspec status:
  - validation failed → **INVALID** (red)
  - `0/0`, or the change is an openspec draft (a required artifact is missing) → **DRAFT** (dim)
  - valid, `0/y` (no tasks done) → **READY** (cyan)
  - valid, `x/y` (some done) → **IN PROGRESS** (yellow)
  - valid, `y/y` (all done) → **DONE** (green)
- Fold the openspec validity into that single state: INVALID overrides, and an openspec draft becomes DRAFT. There is no separate status token — the derived state is authoritative, so a valid change no longer shows a broad `READY`.
- Keep the task progress `done/total` and the artifact count on the status line, toned down beside the prominent state: `STATE · done/total · N Artifacts`.

## Capabilities

### New Capabilities
<!-- None. This refines how the change-list card presents state and task progress. -->

### Modified Capabilities
- `change-list-task-progress`: adds a change **state** derived from task completion and validity (draft/ready/in-progress/done, with INVALID overriding and openspec-draft folding into draft).
- `sidebar-navigation`: the card status line leads with the prominent, color-coded derived state instead of the raw openspec status, followed by the toned-down task progress and artifact count.

## Impact

- **Code**: `sidebar.py` — add a `Change.state` derivation; `format_card_status` builds `STATE · done/total · N Artifacts` (reserving state and progress before the artifact count); `draw_change_card` colors the leading state by a state→color map (INVALID red, DRAFT dim, READY cyan, IN PROGRESS yellow, DONE green) and no longer colors by the raw openspec status.
- **Tests**: `tests/test_sidebar.py` — add tests for the state derivation across the mapping and for the card status-line format and coloring; update the existing status-line format/coloring expectations.
- **Docs**: `README.md` — describe the derived state and its colors on the change card.
- **Out of scope**: the openspec status remains available internally (it feeds INVALID/DRAFT) but is no longer shown as its own card token; the document viewer and other capabilities are unaffected.
