## Context

The sidebar already renders each change as a card whose status line is `STATE · done/total · N Artifacts`, with the state derived in `Change.state` (`sidebar.py`) as `INVALID / DRAFT / READY / IN PROGRESS / DONE`. Input flows through `dispatch_action(action, index)`, shared by keyboard handling and mouse hit testing (`register_hit_target` + `hit_test`). The pane already shells out to Herdr: `report_identity` reads `HERDR_ENV`, `HERDR_PANE_ID`, and `HERDR_BIN_PATH` and runs `herdr pane report-metadata`.

Herdr's socket API exposes exactly the primitives this change needs (confirmed live):
- `herdr pane neighbor --direction left --pane <id>` → JSON with `neighbor_pane_id`.
- `herdr agent get <pane_id>` → JSON with `agent` (e.g. `"claude"`) and `agent_status` (`idle`/`working`/`blocked`/`done`). A `pane_id` is a valid agent target; the session UUID is **not**.
- `herdr agent prompt <pane_id> "<text>"` → types and submits the text. It rejects with `agent_blocked` before sending if the agent is blocked.
- `herdr agent focus <pane_id>` / `herdr pane focus` → focus the neighbour.

## Goals / Non-Goals

**Goals:**
- One derived next action per change, shown as a button at the end of the card status line, guarded by a Herdr check.
- Submit the action to the Claude agent in the pane to the sidebar's left.
- Keep the send logic thin over `herdr`, and keep all decision logic in pure, unit-testable helpers.

**Non-Goals:**
- Targeting any pane other than the immediate left neighbour (no cwd/semantic matching in v1).
- Tracking the agent's progress or auto-refreshing the card when it finishes (the existing file watcher already refreshes state when `tasks.md` changes; a push-based reflect is a possible follow-up).
- A modal confirmation before sending (kept snappy like `v`/`e`; the opsx skills do their own confirmations on the agent side).
- Changing the progress content of the status line or `format_card_status`.

## Decisions

### Target = the immediate left neighbour, confirmed to be a Claude agent
The review pane opens on the right at 50%, so the launching LLM session is the pane to its left. This matches the user's mental model ("the panel next to it") and is unambiguous and visible. Resolution: `herdr pane neighbor --direction left --pane $HERDR_PANE_ID` → `herdr agent get <neighbor_pane_id>`; proceed only if `agent == "claude"` and `agent_status != "blocked"`.
- *Alternative — semantic match by cwd against `herdr agent list`:* more robust across layouts but can send to a pane the reviewer can't see, and must exclude the sidebar's own pane (also `agent:"claude"`). Rejected for v1 as surprising; left neighbour is the contract.

### The button is drawn adjacent to the status line, not baked into `format_card_status`
`format_card_status` stays byte-for-byte as-is (its truncation tests still hold). `draw_change_card` computes the button label first, reserves its width (`len(label) + brackets + a leading space`) from the width passed to `format_card_status`, draws the status text, then draws the button in an accent pair at the reserved right end and registers a hit target over just the button cells. This guarantees the state + progress never yield visually to the button, and the button is only ever drawn when it fully fits.

### State → action and command are pure functions
Add small pure helpers so the mapping is testable without curses or Herdr:
- `running_in_herdr(env) -> bool`: `env.get("HERDR_ENV") == "1" and bool(env.get("HERDR_PANE_ID"))`.
- `agent_action_for_state(state) -> str | None`: `READY→"apply"`, `IN PROGRESS→"investigate"`, `DONE→"archive"`, else `None`.
- `agent_command_for(change) -> str | None`: builds the submitted text —
  - apply → `/opsx:apply <folder_name>`
  - archive → `/opsx:archive <folder_name>`
  - investigate → `Investigate the open tasks in the OpenSpec change '<folder_name>' (<done>/<total> tasks complete) and tell me what is left to finish it.`
  - else `None`
The button label equals the action name (`archive` is the DONE label, per the request — the archive skill syncs specs, so no separate "& sync" wording in the UI).

### Send path and dispatch wiring
A new `dispatch_action` branch `"agent_action"` (with the card `index`) selects that change and calls an impure `send_agent_action(change)` method that: guards `running_in_herdr`; builds the command; resolves + validates the neighbour; runs `herdr agent prompt`; on success `say(...)` a confirmation and `herdr agent focus`; on any failure `say(...)` the reason and change nothing. All `herdr` calls use `HERDR_BIN_PATH` with short timeouts and `check=False`, mirroring `report_identity`/`validate`.

### Keyboard parity
Because in-pane mouse capture can be toggled off (`m`), bind a key that triggers the **selected** change's action, and advertise it in the main footer with the selected change's current action label (e.g. `a apply` / `a investigate` / `a archive`), shown only inside Herdr and only when the selected change has an action. Chosen key: `a` ("act"). The footer hint is itself clickable and dispatches the same `agent_action` for the selected index.

## Risks / Trade-offs

- **Wrong-pane send** (left neighbour isn't the intended agent) → we confirm `agent == "claude"` and report + focus after sending so a mistake is immediately visible; no silent fire-and-forget.
- **Narrow panes** (button + status don't both fit) → button is only drawn when it fits after reserving its width; the state/progress always win, so the worst case is simply no button (still reachable by keyboard).
- **Sending to a `working` agent** → `agent prompt` accepts it and queues into the active turn; acceptable, and the post-send focus makes it visible. Only `blocked` is pre-empted (both by us and by `agent prompt` itself).
- **Change-name ambiguity across multiple `openspec/` roots** → we send the unprefixed `folder_name`; the neighbour resolves it in its own cwd, which is normally the same repo. Cross-root collisions are a rare edge; out of scope for v1.
- **Coupling to opsx skills on the neighbour** → apply/archive assume the neighbour is a Claude Code session with the opsx skills; detection is limited to `agent == "claude"`. A Claude agent without those skills would receive an unknown slash command; acceptable and visible.
