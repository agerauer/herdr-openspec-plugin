## Context

See proposal.md — Why. `Change.status` returns `INVALID` (validation failed) / `DRAFT` (a required artifact missing) / `READY` (otherwise). The card status line is built by `format_card_status(change, width)` as `STATUS · N Artifacts · done/total` and drawn by `draw_change_card`, which paints the whole line dim and overlays the leading `change.status` word in a color chosen from `{READY: yellow, INVALID: red, else dim}`. `tasks_done`/`tasks_total` come from parsing `tasks.md` checkboxes; `missing_required` counts required artifacts that do not exist.

## Goals / Non-Goals

**Goals:**
- One prominent, informative state per card, derived from task progress and validity.
- Keep `done/total` and the artifact count visible but toned down.

**Non-Goals:**
- A separate openspec-status token (folded into the derived state).
- Any change outside the change-list card (viewer, discovery, sorting).

## Decisions

### Decision: Derive state on the Change, folding in validity

Add `Change.state`, computed in order: `INVALID` if `validation == "invalid"`; else `DRAFT` if `tasks_total == 0` or `missing_required`; else `READY` if `tasks_done == 0`; else `IN PROGRESS` if `tasks_done < tasks_total`; else `DONE`. This is the single state the card shows; the raw `status` is no longer displayed but remains available (it feeds the INVALID/DRAFT branches via `validation`/`missing_required`).

- **Why:** The reviewer's real question is progress, which the task counts already encode; validity (INVALID/openspec-draft) still matters, so it overrides/folds into the same state rather than competing as a second token (chosen "fold in" over a separate dim tag).

### Decision: Status line is `STATE · done/total · N Artifacts`, state colored

`format_card_status` returns `f"{state} · {done}/{total} · {N} Artifacts"`, reserving the state and progress before the artifact count when the line is too narrow (drop/trim the artifact count first, keep the complete `done/total`). `draw_change_card` draws the whole line dim, then overlays the leading `state` substring bold in a state→color map: `INVALID` red (pair 4), `DRAFT` dim, `READY` cyan (pair 1), `IN PROGRESS` yellow (pair 3), `DONE` green (pair 2). The overlay colors `status_line[:len(state)]`, which correctly spans the two-word `IN PROGRESS`.

- **Why:** Reuses the existing dim-line + colored-overlay drawing; the state leads so it reads first; progress stays legible per the existing constrained-width guarantee.

## Risks / Trade-offs

- **`DRAFT` and the raw openspec `DRAFT` share a word** but now mean "not started / not ready" (0/0 or missing artifact) → acceptable; they coincide by intent, and there is only one token now.
- **Losing the always-on `READY`** → intended: a valid change now shows its progress (READY/IN PROGRESS/DONE) instead of a blanket READY.
- **Two-word `IN PROGRESS` widens the status line** → the constrained-width path trims the artifact count first and keeps state + `done/total`.

## Migration Plan

Add `Change.state`; rewrite `format_card_status` to the new order with state+progress reserved; update `draw_change_card`'s color map to key on `state`. Update the affected `tests/test_sidebar.py` status-line and card tests and add state-derivation tests. Update `README.md`. No persisted state; rollback is a straight revert.

## Open Questions

- The exact color for each state is a presentation choice settled in code (reusing existing pairs); it does not affect the specs or task breakdown.
