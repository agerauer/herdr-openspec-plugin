## 1. Open a change from its name

- [x] 1.1 Add the card-scoped action that selects a change by index (change_index, artifact_index, focus — as the `agent_action` branch does) and then opens its Proposal via `open_artifact_by_key("proposal")`, so a missing Proposal reports "Artifact does not exist yet" and leaves the viewer closed.
- [x] 1.2 In `draw_change_card`, register a hit target for the drawn name: row `top`, column 1 through `1 + len(<the string passed to put>)`, bound to that action with the card's `index`. Register it from inside `draw_change_card` so it precedes the card-wide `select_change` target and wins `hit_test`, matching how the action button already works.

## 2. Tests

- [x] 2.1 Clicking a change name opens that change's Proposal in the viewer.
- [x] 2.2 Clicking the name of a change that is not currently selected selects it first, and the document that opens is that change's Proposal — not the previously selected change's.
- [x] 2.3 Clicking the name of a change whose Proposal does not exist selects it, reports that the artifact does not exist yet, and leaves the viewer closed.
- [x] 2.4 Clicking a card line that is not the name (status line away from the button, or the description) still only selects, opening nothing; and clicking past the end of a short name on the name row still only selects.

## 3. Docs and verification

- [x] 3.1 Add the new click to the Controls table in `README.md` ("Left-click a change's name | Open that change's Proposal"), leaving the existing card-click row accurate for the other lines.
- [x] 3.2 Run `python3 -m unittest discover -s tests -v` and confirm the whole suite passes, including the existing card-click and agent-button click tests — the new target must not shadow the action button or the card-wide selection.
- [x] 3.3 Run `openspec validate make-change-titles-clickable --strict` and confirm it passes.
