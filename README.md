# OpenSpec Review for Herdr

A narrow keyboard-and-mouse review pane for active [OpenSpec](https://openspec.dev/) changes. It keeps proposal, specification, design, and task review in the same terminal workspace as your coding agents.

## What it shows

- Every active change from the workspace `openspec/` tree and from OpenSpec directories at most two levels below it (for example `nxt/openspec` and `apps/nxt/openspec`)
- Nested changes prefixed with the project path using a spaced middle dot (`nxt · add-login`); root-level changes keep their unprefixed name
- Up to 15 changes at once in tall panes, reduced automatically when the pane needs the space for details and artifacts
- Worktree-touched changes grouped at the top and marked with `◆`, with the most likely one initially selected
- Proposal, Design, and Tasks first, followed by deterministically sorted Specs
- Total artifact counts, with more than four artifact rows shown when pane height permits
- Missing and optional artifacts
- ADDED, MODIFIED, REMOVED, and RENAMED requirement counts
- Per-change `X/Y` task completion directly in every change-list row
- `openspec validate` results on demand, run in the change's own OpenSpec project

## Install for local development

Requirements: Herdr 0.8+, OpenSpec, and Python 3 on macOS or Linux.

```sh
herdr plugin link .
herdr plugin action invoke herdr.openspec-review.open-sidebar
```

The action uses the invoking pane's foreground directory, resolves the Git workspace (or the highest ancestor with an `openspec/` directory), and opens the review pane on the right. The pane process stays rooted in the plugin checkout while the selected workspace is passed separately, so it works from any Herdr workspace. Invoking it again focuses the existing review pane for that workspace.

## Worktree-aware ordering

When the selected workspace is in Git, the sidebar compares every discovered `openspec/changes/` tree with the merge base of the repository's default branch. It includes committed branch differences, staged and unstaged edits, and untracked files. Touched active changes appear before untouched changes and carry a `◆` marker, regardless of which OpenSpec root they come from.

Within the touched group, an exact normalized match between the unprefixed change folder name and the branch leaf or worktree directory name ranks first, followed by a match where that context name contains the complete hyphen-delimited folder name, then most recent activity and finally the displayed change name. The highest-ranked touched change is selected when the pane first opens. Refreshes preserve the current selection while it still exists.

The base resolver checks the remote default branch, then `origin/main`, local `main`, `origin/master`, and local `master`. If the project is not a Git worktree or Git/base inspection fails or times out, the pane still opens with normal alphabetical ordering and no worktree markers.

To bind it in `~/.config/herdr/config.toml`:

```toml
[[keys.command]]
key = "prefix+o"
type = "plugin_action"
command = "herdr.openspec-review.open-sidebar"
description = "Open OpenSpec review"
```

Then run `herdr server reload-config`.

## Controls

| Input | Action |
| --- | --- |
| `↑` / `↓`, `j` / `k` | Move list selection; scroll an open document by one wrapped line |
| `Page Up` / `Page Down` | Scroll an open document by one visible page |
| `Tab`, `→`, `l` | Toggle focus between changes and artifacts |
| `←`, `h` | Return from a document, or focus the change list from the main view |
| `Esc` | Return from a document; from the main artifact list, focus the selected change |
| `Enter` | Move from the selected change to its artifacts, or open the selected artifact |
| `p`, `d`, `t` | From the change list, open Proposal, Design, or Tasks directly |
| `v` | Validate the selected change with OpenSpec |
| `e` | Edit the open artifact with VS Code when `code` is on `PATH`, otherwise `vi` |
| `r` | Refresh now (the pane also watches for changes) |
| `q` | Close the review pane |
| Left-click a change | Select it and show its details and artifacts |
| Left-click an artifact | Select and open it, or report that it does not exist yet |
| Left-click the viewer's top back label | Return to the selected artifact in the main view |
| Left-click a footer hint | Run the displayed open, validate, back, edit, or close action |
| Mouse wheel up/down | Scroll an open document by one wrapped line in either direction per event |

## Test

```sh
python3 -m unittest discover -s tests -v
```
