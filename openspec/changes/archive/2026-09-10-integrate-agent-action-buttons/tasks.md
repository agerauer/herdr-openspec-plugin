## 1. Pure decision helpers

- [x] 1.1 Add `running_in_herdr(env)` returning `True` only when `env["HERDR_ENV"] == "1"` and `env["HERDR_PANE_ID"]` is set; unit-test both env shapes (in/out of Herdr) in `tests/test_sidebar.py`.
- [x] 1.2 Add `agent_action_for_state(state)` mapping `READY→"apply"`, `IN PROGRESS→"investigate"`, `DONE→"archive"`, and `DRAFT`/`INVALID`/unknown→`None`; unit-test every state.
- [x] 1.3 Add `agent_command_for(change)` returning `/opsx:apply <folder_name>` for apply, `/opsx:archive <folder_name>` for archive, the investigate prompt (naming the change and `done/total`) for investigate, and `None` otherwise; unit-test each branch and the `None` case, asserting `folder_name` (not the display name) is used.

## 2. Button rendering on the card status line

- [x] 2.1 In `draw_change_card`, when `running_in_herdr(os.environ)` and the change has an action, reserve the button's width, draw the existing status text in the remaining width, then draw a bracketed action-labelled button (`apply`/`investigate`/`archive`) in an accent pair at the end of the status row; leave the status text unchanged when there is no action or not in Herdr. Verify the state+progress text is never truncated by the button.
- [x] 2.2 Register a hit target over the button cells with action `"agent_action"` and the change's list index. Verify via a rendered-buffer/hit-target test that a click on the button cells resolves to `agent_action` for the right index and that non-actionable/outside-Herdr cards register no such target.
- [x] 2.3 Add tests asserting the button is present with the correct label per state under a simulated Herdr env and absent for `DRAFT`/`INVALID` and when not in Herdr.

## 3. Triggering and sending

- [x] 3.1 Add a `dispatch_action` branch for `"agent_action"` that selects the change at `index` and calls `send_agent_action(change)`; verify selection happens even when the clicked card was not selected.
- [x] 3.2 Implement `send_agent_action(change)`: guard `running_in_herdr`; build the command with `agent_command_for`; resolve the left neighbour via `herdr pane neighbor --direction left --pane $HERDR_PANE_ID`; validate it with `herdr agent get <pane>` (`agent == "claude"`, `agent_status != "blocked"`); submit with `herdr agent prompt <pane> <command>`; on success `say` a confirmation and run `herdr agent focus <pane>`; on each failure mode `say` a distinct message and send nothing. Use `HERDR_BIN_PATH`, short timeouts, `check=False`.
- [x] 3.3 Unit-test `send_agent_action`'s branching with the `herdr` calls stubbed: asserts the exact `herdr agent prompt` argv for apply/investigate/archive, and asserts no prompt is sent (and the right message shown) for no-neighbour, non-claude neighbour, and blocked agent.

## 4. Keyboard parity and footer

- [x] 4.1 Bind the `a` key (main view) to dispatch `"agent_action"` for the selected change; verify the key triggers a send for an actionable selected change and is a no-op for a non-actionable one.
- [x] 4.2 Show a clickable main-footer hint reflecting the selected change's action label (`a apply`/`a investigate`/`a archive`) only inside Herdr and only when the selected change has an action; verify it is absent otherwise and that clicking it dispatches `agent_action` for the selected index.

## 5. Docs and full verification

- [x] 5.1 Update `README.md`: document the in-card action button, the `READY→apply` / `IN PROGRESS→investigate` / `DONE→archive` mapping, the Herdr-only guard, the left-neighbour target, and the `a` shortcut.
- [x] 5.2 Run `python3 -m unittest discover -s tests -v` and confirm the whole suite passes; run `openspec validate integrate-agent-action-buttons --strict` and confirm it passes.
