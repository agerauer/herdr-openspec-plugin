## Context

`draw_viewer` currently renders a single back-labeled title on row 0, the change name on row 1, and the document from row 3. `p`, `d`, and `t` call `open_artifact_by_key` only when the change list has focus and no document is open; the existing sidebar-navigation spec requires those keys to be ignored in the viewer. Specifications are later artifact rows with `spec:` keys and have no shortcut. See `proposal.md` for motivation and the delta specs for required behavior.

The viewer must remain dependency-free and keep line/page scrolling, edit, and back working in a narrow pane.

## Goals / Non-Goals

**Goals:**

- Add a testable header tab layout that reuses existing hit-target registration.
- Route `p`, `d`, `t`, and `s` through the same open-or-missing path already used by the change list.
- Cycle specification artifacts in the same deterministic order the artifact list already uses.

**Non-Goals:**

- Replacing the main-view artifact list with tabs.
- Per-specification tab labels in the header.
- Configurable key bindings or tab order.
- Changing document wrapping, edit, validate, or change-list navigation except for the added `s` shortcut.

## Decisions

### Keep four tabs and cycle specs on `s`

The header will show Proposal, Design, Tasks, then one tab per specification using the short spec label (the path after `Spec ·`). `s` from the change list opens the first `spec:` artifact. In the viewer, `s` rotates through specifications only: a single spec stays put, and multiple specs wrap from last to first without landing on Proposal. Clicking a spec tab opens that spec.

If the tab strip overflows, trailing labels are omitted, but the window shifts so the selected tab stays visible and marked.

Alternative considered: a single Specs tab. In a narrow pane that tab is the first to clip, so an open spec appears unmarked and looks like Proposal.

### Place tabs on the existing title row beside the back control

Row 0 will keep a compact `‹` back target, then the four tabs. Row 1 remains the change name. Content still starts at row 3 so scrolling math (`height - 5`) stays valid. The selected tab uses reverse or bold treatment similar to a selected list row. Missing core artifacts still occupy their tab slot so `p`/`d`/`t` have a stable target.

Tab layout will follow the footer-segment pattern: only complete labels that fit the remaining width are drawn and registered. Overflowing tabs are omitted rather than truncated mid-label.

Alternative considered: a dedicated tab row. That shrinks the document viewport by one line in every pane, including the 12-row minimum.

### Reuse open-or-missing dispatch for keys and clicks

Viewer shortcuts and tab clicks will select the artifact index and call the existing open path so missing files still report "Artifact does not exist yet" without closing the current document. Switching to a different existing artifact resets `viewer_offset` to 0. Pressing the shortcut for the already open artifact leaves the offset unchanged.

`s` with zero specification documents is the missing-artifact path. A single specification makes `s` a no-op besides selecting that spec.

Left and Right in the viewer walk existing documents in Proposal → Design → Tasks → specification order, skipping missing core files. Left from the first existing document closes the viewer. Right from the last existing document, including the last specification, stays put and does not wrap. `h`/`l` keep their usual pairing with the arrows; Escape and the header/footer back controls still leave the viewer from any tab.

Alternative considered: close the viewer when the target is missing. That is more disruptive than the current change-list behavior.

## Risks / Trade-offs

- [Four tab labels plus the back control will not fit in very narrow panes] → omit incomplete trailing tabs and keep back plus any fully visible tabs clickable.
- [Specs tab does not name the current specification] → keep the change name on row 1 and the spec title in the selected artifact model; do not add a fifth header row.
- [Cycling wraps without a visible spec index] → accept wrap-around; the artifact list remains available for random access.
- [Enabling shortcuts in the viewer changes a previously ignored-key behavior] → document the new bindings; keep the artifact-list ignore so list navigation keys stay exclusive.

## Migration Plan

No data migration is required. Relink or reopen the plugin pane to load tabs. Rollback is a revert of viewer header rendering, shortcut handling, tests, and README.

## Open Questions

None. Four-tab layout, Specs cycling, missing-artifact handling, and shortcut scope are specified above.
