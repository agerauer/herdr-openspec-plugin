## 1. Viewer tab header

- [x] 1.1 Add a pure tab-layout helper that places `‹` then Proposal, Design, Tasks, and Specs on the viewer title row, marks the selected tab, and omits incomplete trailing labels, and verify unit tests cover a wide header, a pane that fits only back plus two tabs, and no hit target for a clipped tab.
- [x] 1.2 Render those tabs in `draw_viewer`, keep the back affordance clickable, register tab hits, and verify rendering tests cover a selected core tab, a selected Specs tab while a specification is open, and an unchanged back-click path.

## 2. Tab and shortcut switching

- [x] 2.1 Dispatch tab clicks through the existing open-or-missing path so an existing Design tab opens Design, a missing Design tab reports the artifact is missing without closing the current document, Specs from a core document opens the first spec, and Specs while viewing a spec leaves that spec selected, and verify tests cover each of those four cases.
- [x] 2.2 Enable `p`, `d`, and `t` in the document viewer as well as the change list, leave those keys ignored while the artifact list has focus, and verify tests cover switching from an open Proposal to Design, a missing-target report that keeps the current document, and unchanged artifact-list selection.
- [x] 2.3 Add `s` to open the first specification from the change list, cycle specifications in deterministic order with wrap in the viewer, and report missing when no spec document exists, and verify tests cover first-spec open, wrap from last to first, a single-spec no-op besides selection, and the missing-spec message.
- [x] 2.4 Make Left/Right (and `h`/`l`) move through existing viewer documents in tab order, back out from the first document, and stay on the last spec when there is no next spec, and verify tests cover Proposal→Design, spec→next spec, last-spec no-op, and Left from Proposal closing the viewer.

## 3. Documentation and verification

- [x] 3.1 Update the README controls for viewer tabs, `p`/`d`/`t`/`s`, and Left/Right tab movement, including Specs cycling, and verify the table matches the implemented bindings.
- [x] 3.2 Run `python3 -m unittest discover -s tests -v`, validate the OpenSpec change, and perform a live Herdr smoke test that opens a change with multiple specs and switches via tabs and `p`/`d`/`t`/`s`.
