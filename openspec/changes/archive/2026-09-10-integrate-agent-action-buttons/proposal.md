## Why

Reviewing a change in the sidebar and acting on it are two disconnected steps today: the reviewer reads the proposal here, then switches to the coding-agent pane and hand-types `/opsx:apply`, `/opsx:archive`, or a "what's left?" prompt. Herdr's socket API already lets one pane submit a prompt to the agent in another pane, so the sidebar can offer the single next action for each change inline and drive the neighbouring session directly.

## What Changes

- Add a per-change action affordance at the end of each card's status line that submits the change's next action to the coding agent running in the pane to the sidebar's left.
- Show exactly **one** button per card, chosen from the card's derived state — nothing else is offered:
  - `READY` → **apply** (`/opsx:apply <change>`)
  - `IN PROGRESS` → **investigate** (a plain-language prompt to look at the open tasks)
  - `DONE` → **archive** (`/opsx:archive <change>`, which also syncs specs)
  - `DRAFT` / `INVALID` → no button
- Guard the whole feature behind an "is this running inside Herdr" check: outside Herdr (standalone/dev/tests) no button is shown and nothing is sent.
- Resolve the target as the **left neighbour pane**, confirm it is a Claude agent, and submit via `herdr agent prompt`; report a clear one-line message when there is no usable neighbour or it is busy, and focus the agent after a successful send so the reviewer can watch and approve.
- Make the action reachable by keyboard as well as click (for when in-pane mouse capture is toggled off), acting on the selected card.

## Capabilities

### New Capabilities
- `change-agent-actions`: derive a single next action from a change's state, present it as a guarded in-card button (and keyboard shortcut), and submit it to the coding agent in the neighbouring Herdr pane.

### Modified Capabilities
<!-- None. The card status line's progress rendering is unchanged; the action button is an adjacent affordance owned by the new capability. -->

## Impact

- `sidebar.py`: new pure helpers (Herdr detection, state→action/command mapping, button geometry), a `draw_change_card` addition, a new `dispatch_action` branch and hit target, a keyboard binding, and a `herdr agent`-based send method.
- `tests/test_sidebar.py`: unit tests for the pure helpers and the button's presence/labelling per state and Herdr guard.
- `README.md`: document the new button, its state mapping, and the keyboard shortcut.
- Runtime dependency on Herdr's `pane neighbor` / `agent get` / `agent prompt` socket commands (already present; `HERDR_BIN_PATH`/`HERDR_PANE_ID` already used by `report_identity`). No new Python packages.
