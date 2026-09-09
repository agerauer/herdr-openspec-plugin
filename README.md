# OpenSpec Review for Herdr

A narrow keyboard-and-mouse review pane for active [OpenSpec](https://openspec.dev/) changes. It keeps proposal, specification, design, and task review in the same terminal workspace as your coding agents.

## What it shows

- Every active change from the workspace `openspec/` tree and from OpenSpec directories at most two levels below it (for example `nxt/openspec` and `apps/nxt/openspec`)
- Nested changes prefixed with the project path using a spaced middle dot (`nxt · add-login`); root-level changes keep their unprefixed name
- Each change as an inline card — bold name, a `STATUS · N Artifacts · done/total` line, and the change's description — shown for every change, not only the selected one
- Up to 15 change cards in tall panes, reduced automatically to fit; the selected card stays in view as you move
- Worktree-touched changes grouped at the top with their names shown in an accent color (the most likely one initially selected); no separate marker glyph
- A document viewer with a color-coded tab bar — the standard artifacts (Proposal, Design, Tasks), any non-standard `.md` documents in the change folder (shown after Tasks, before specs), and one tab per specification each in their own color; the open document is marked, the tab bar wraps onto more rows when needed, and the change name heads the view above the tabs
- `p`, `d`, `t`, and `s` switch among the standard artifacts and specs, Enter opens the Proposal, and Left/Right move through every tab including non-standard documents
- Documents rendered as formatted Markdown: color-coded headings, **bold**, *italic*, inline and fenced code, links, nested and ordered lists with hanging indents, and pipe tables that shrink to fit the pane
- Per-change status, artifact count, and `X/Y` task completion on each card's status line
- `openspec validate` results on demand, run in the change's own OpenSpec project

## Install for local development

Requirements: Herdr 0.8+, OpenSpec, and Python 3 on macOS or Linux.

```sh
herdr plugin link .
herdr plugin action invoke herdr.openspec-review.open-sidebar
```

The action uses the invoking pane's foreground directory, resolves the Git workspace (or the highest ancestor with an `openspec/` directory), and opens the review pane on the right. The pane process stays rooted in the plugin checkout while the selected workspace is passed separately, so it works from any Herdr workspace. Invoking it again focuses the existing review pane for that workspace.

## Worktree-aware ordering

When the selected workspace is in Git, the sidebar compares every discovered `openspec/changes/` tree with the merge base of the repository's default branch. It includes committed branch differences, staged and unstaged edits, and untracked files. Touched active changes appear before untouched changes and have their names shown in an accent color, regardless of which OpenSpec root they come from.

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
| `↑` / `↓`, `j` / `k` | Move the change selection; scroll an open document by one wrapped line |
| `Page Up` / `Page Down` | Scroll an open document by one visible page |
| `→`, `l` | Open the selected change's Proposal; in the document viewer, open the next tab or next spec if any |
| `←`, `h` | In the document viewer, open the previous tab, or return if Proposal is open |
| `Esc` | Return from a document to the main view |
| `Enter` | Open the selected change's Proposal in the document viewer |
| `p`, `d`, `t` | Open Proposal, Design, or Tasks from the change list or switch to them in the document viewer |
| `s` | Open the first specification from the change list; in the document viewer, stay on a single spec or rotate through specs |
| Left-click a viewer tab | Switch to that artifact, or report that it does not exist yet |
| `v` | Validate the selected change with OpenSpec |
| `e` | Open the selected change's whole folder in VS Code (requires `code` on `PATH`), from both the change list and the document viewer |
| `r` | Refresh now (the pane also watches for changes) |
| `q` | Close the review pane |
| Left-click a change card | Select that change |
| Left-click the viewer's top back label | Return to the selected artifact in the main view |
| Left-click a footer hint | Run the displayed open, validate, back, edit, or close action |
| Mouse wheel up/down | Scroll an open document by one wrapped line in either direction per event |

## Test

```sh
python3 -m unittest discover -s tests -v
```
