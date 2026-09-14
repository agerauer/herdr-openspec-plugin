## Why

Opening a change's Proposal from the change list takes two steps today: click the card to select it, then press Enter (or `p`, or click the footer's document-keys hint). The change name is the obvious thing to click to read a change — it is the card's heading and the thing a reviewer is looking at — but clicking it currently does the same as clicking anywhere else on the card: it only moves the selection. Making the name open the Proposal collapses the common "what is this change about?" gesture into one click.

## What Changes

- Left-clicking a change's **name** in the change list SHALL select that change and open its Proposal in the document viewer, in one action. Clicking the card's other lines keeps its current behaviour: select only.
- When the clicked change has no Proposal file yet, the sidebar reports that it does not exist, exactly as Enter and `p` already do, and stays on the change list.
- Clarify the card requirement's click sentence. It currently reads that left-clicking **any line** of a card selects that change, which this change contradicts — and which the existing agent-action button already contradicts, since clicking that button submits an action rather than merely selecting. The requirement is reworded so a card click selects the change *except* where the card draws a more specific target (the change name, or the action button), which performs its own action after selecting. **No behaviour change for the button**; this only makes the written requirement true of what already ships.

## Capabilities

### New Capabilities
<!-- None. This extends how an existing card responds to the mouse. -->

### Modified Capabilities
- `sidebar-navigation`: the "Change rows render as inline cards" requirement gains the change name as a distinct mouse target that opens the Proposal, and its "any line selects" clause is corrected to account for the card's more specific targets.

## Impact

- `sidebar.py`: register a hit target over the drawn change name in `draw_change_card`, and add the action that selects a change by index and opens its Proposal. The card-wide `select_change` target stays as the fallback; the name target is registered first so it wins, which is how the agent-action button already works.
- `tests/test_sidebar.py`: cover clicking a name (opens the Proposal), clicking a *different* change's name (selects it first, then opens that change's Proposal), clicking a name whose Proposal is missing (reports it, viewer stays closed), and clicking a non-name line (still select-only).
- `README.md`: add the new click to the Controls table.
- No new dependencies. No keyboard behaviour changes.

### Assumptions recorded (worth a look at apply time)

- **The target is the drawn name text, not the whole first row.** Clicking blank space to the right of a short name keeps today's select-only behaviour, so a click aimed at selecting a change is less likely to open the viewer unexpectedly.
- **No new styling.** The name keeps its existing bold/worktree-colour treatment rather than gaining an underline or other link affordance; a terminal pane has no hover state to reveal one, the whole card is already clickable, and the established preference here is understated visuals.
