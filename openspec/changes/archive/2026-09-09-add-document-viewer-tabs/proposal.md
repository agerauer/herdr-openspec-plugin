## Why

Reviewing a change means jumping among proposal, design, tasks, and specs, but the document viewer shows a single title and only `p`, `d`, and `t` from the change list. Switching artifacts requires leaving the viewer, and specifications have no keyboard shortcut at all.

## What Changes

- Show Proposal, Design, Tasks, and Specs tabs in the document viewer.
- Let `p`, `d`, and `t` switch those core artifacts while a document is open, using the same keys as the change list.
- Add `s` to open the first specification from the change list and to cycle through specifications in the document viewer.
- Make visible tabs clickable, with missing artifacts reported the same way as the artifact list.
- Keep the existing header back affordance, scrolling, edit, and footer actions.

## Capabilities

### New Capabilities

- `document-viewer-tabs`: Defines the document-viewer's Proposal, Design, Tasks, and Specs tabs, including mouse activation and specification cycling.

### Modified Capabilities

- `sidebar-navigation`: Direct artifact shortcuts work in the document viewer as well as the change list, and `s` opens or cycles specifications.

## Impact

- `sidebar.py`: viewer header tab layout and hit targets, `s` cycling, and shortcut handling while a document is open.
- `tests/test_sidebar.py`: tab rendering, click switching, `p`/`d`/`t`/`s` in the viewer, spec cycling, and missing-artifact shortcuts.
- `README.md`: document-viewer tabs and updated shortcut descriptions.
- No OpenSpec file-format changes, Herdr API changes, or new runtime dependencies.
