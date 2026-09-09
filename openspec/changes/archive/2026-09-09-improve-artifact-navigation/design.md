## Context

Artifact discovery currently appends Proposal, every spec, Design, and Tasks; the layout reserves at most four artifact rows before allocating change rows. The viewer's top `‹` label is rendered without a hit target, Escape shares a state-dependent back action, and downward wheel support depends on button-5 constants that this Python curses build does not expose. Editing suspends curses and invokes `$EDITOR`, defaulting to `vi`. See `proposal.md` for motivation and `specs/sidebar-navigation/spec.md` for the behavior contract.

The implementation remains a dependency-free single-process curses UI, must preserve narrow-pane usability, and must not make optional VS Code availability a startup requirement.

## Goals / Non-Goals

**Goals:**

- Give artifact discovery and navigation one stable, testable ordering and direct lookup by core key.
- Use otherwise unused vertical space for additional artifact rows without weakening the existing 15-change target in tall panes.
- Route keyboard, footer, and header mouse interactions through explicit semantic actions with predictable focus transitions.
- Recognize the wheel-down encodings used when Python exposes no button-5 constants.
- Select an editor with an argv-based executable check and no shell interpolation.

**Non-Goals:**

- User-configurable artifact ordering, artifact viewport limits, or shortcut bindings.
- Direct shortcuts for individual specification files.
- Embedding an editor or adding a VS Code extension/API dependency.
- Changing Markdown rendering, page-scroll size, change ordering, or task progress calculation.

## Decisions

### Build artifacts in core-first order and index them by key

Discovery will append Proposal, Design, and Tasks before adding specs sorted by their relative path. When no spec exists, the current required/optional Specifications placeholder will be appended in the spec section after Tasks. A small key lookup will power direct navigation without relying on row positions, so missing artifacts and any number of specs use the same selection and open path.

Alternative considered: reorder only during rendering. That would make displayed indexes diverge from hit-target and keyboard indexes and create two orderings to maintain.

### Preserve current layout priorities, then spend surplus height on artifacts

Layout calculation will keep its minimum one change/one artifact behavior, goal limit, initial reservation of up to four artifact rows, and change expansion up to 15 rows. After those allocations, any remaining content rows will expand the artifact window up to the total artifact count. The header will render `ARTIFACTS (N)` from the full model count, while the centered window continues to keep the selected item visible.

Alternative considered: remove the artifact limit before allocating change rows. That could allow a spec-heavy change to collapse the change list in otherwise comfortable panes and conflict with the existing 15-change behavior.

### Separate viewer back from main-view focus return

The viewer header will register a clipped hit target over the visible back label and dispatch the same viewer-back action as the footer. In the main view, Escape will explicitly focus changes; it will not depend on whether a viewer was previously present. Closing a document will retain the selected artifact so the user returns to the same location, while a second Escape from artifact focus moves to the selected change.

Alternative considered: keep a single implicit back branch for every state. The current state-dependent behavior is harder to test and is the source of the reported focus inconsistency.

### Treat direct core shortcuts as change-list-only actions

`p`, `d`, and `t` will resolve the corresponding artifact key for the selected change, set its artifact index, and reuse the normal open-or-missing behavior. The bindings are active only in the main view while changes have focus so they cannot unexpectedly replace a document being read or interfere with artifact-list navigation.

Alternative considered: make the shortcuts global. Global keys are faster in some cases but make ordinary document or artifact interaction less predictable and exceed the requested change-list scope.

### Normalize wheel direction before applying scroll

A pure wheel-direction helper will map all exposed curses pressed/clicked/released constants, ncurses-compatible raw button-5 bits, and the `REPORT_MOUSE_POSITION` value that this ncurses/Python combination reports for an encoded button-5 wheel-down event. Mouse handling will request one signed line movement from that helper, keeping direction recognition separate from offset clamping. Tests will cover upward and downward states independently, including the exact no-button-5 environment observed on this platform.

Alternative considered: continue treating button-4 release as the only fallback for downward movement. Release reporting varies by terminal transport and has not worked in the live pane.

### Prefer `code` by executable discovery and otherwise run `vi`

The edit action will use an executable lookup for `code`; when found, it will launch `code <artifact-path>`, otherwise `vi <artifact-path>`. Both commands will use argv arrays and the project working directory. Curses teardown/refresh and forced reload will remain around the launch so terminal `vi` works and changes appear after the editor returns. `$EDITOR` will no longer decide this action because the requested order is specifically VS Code then `vi`.

Alternative considered: prefer `$EDITOR` before `code`. That would preserve configurability but would not guarantee the requested VS Code preference.

## Risks / Trade-offs

- [Raw mouse masks differ outside ncurses-compatible terminals] → isolate the fallback in one helper, prefer exposed curses constants, and ignore unrecognized states without changing the view.
- [More artifact rows can reduce whitespace and make dense panes feel busier] → allocate only surplus rows after existing core layout priorities and retain the centered viewport.
- [Mnemonic keys may be pressed accidentally while browsing artifacts] → enable them only while the change list has focus and document the scope.
- [VS Code can be installed without its `code` command on `PATH`] → treat that case as unavailable and use the explicit `vi` fallback.

## Migration Plan

No data migration or configuration change is required. Reopening or refreshing the linked pane activates the new navigation behavior. Rollback consists of reverting the sidebar, tests, and README changes; OpenSpec artifacts remain compatible.
