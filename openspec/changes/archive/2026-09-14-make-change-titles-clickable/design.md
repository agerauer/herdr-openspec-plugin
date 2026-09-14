## Context

See proposal.md — Why. Mechanically: `draw_main` draws each card with `draw_change_card(top, width, item, selected, index)` and then registers one card-wide target, `register_hit_target(top, 1, top + 3, max(1, width), "select_change", index)`. `hit_test` returns the **first** target containing the point, and `draw_change_card` runs before that registration, so any target the card registers itself takes precedence over the card-wide one. The agent-action button already relies on this: it registers a narrow target on the status line inside `draw_change_card` and therefore wins over `select_change`.

The name is drawn once, at row `top`, column 1, as `format_card_name(change, width - 2, selected)` — a selection marker, a space, and the truncated name.

## Goals / Non-Goals

**Goals:**
- Clicking the drawn change name selects that change and opens its Proposal, in one gesture.
- Leave every other click on the card behaving exactly as it does now.

**Non-Goals:**
- No change to keyboard behaviour (`Enter`, `p`, arrows) or to the footer hints.
- No new visual affordance for the name (see the proposal's recorded assumptions).
- Not making other card lines open anything (the status line belongs to the action button; the description stays inert).

## Decisions

### The target covers the drawn name text, not the whole first row
Register the target from column 1 to `1 + len(drawn_name)` on row `top` only, using the same string that was drawn so the region and the glyphs always agree — including when the name is truncated at narrow widths, and including the leading selection marker, which reads as part of the title block.

- *Alternative — the full first row (`left=1, right=width`):* a larger, easier target, but it converts a click on empty space beside a short name from "select" into "open the viewer". Selecting a change without opening it stays a common gesture, so the quieter region is the better default. Rejected, but this is a one-line change if it feels too fussy in use.

### Reuse the registration-order precedence rather than adding priority
Register the name target inside `draw_change_card`, like the action button, so the existing first-match-wins ordering resolves it against the card-wide `select_change` target. No change to `hit_test`, `clipped_hit_target`, or the target model.

### One new action that selects by index, then opens
Add a card-scoped action (e.g. `open_change`) carrying the card's `index`, which sets `change_index`/`artifact_index`/`focus` and then calls `open_artifact_by_key("proposal")`. This mirrors the existing `agent_action` branch, which already has to select-by-index before acting.

- *Alternative — reuse the existing `open` action:* `open` acts on `self.change` and carries no index, so a click on a non-selected card would open the **previously** selected change's Proposal. It would need the same select-first step anyway, and changing `open` in place would also affect the footer hint that dispatches it. Rejected.

Opening goes through `open_artifact_by_key`, so the missing-Proposal path (`"Artifact does not exist yet"`) and the viewer-freshness re-read on open both come for free.

## Risks / Trade-offs

- **A click meant to select now opens the viewer** when it lands on the name. Mitigated by keeping the region to the drawn text; `Esc`/`←` returns immediately.
- **Truncated names shrink the target** at narrow widths, down to a few columns. Acceptable: the card-wide select target still covers the rest of the row, so the click is never lost, it just selects instead.
