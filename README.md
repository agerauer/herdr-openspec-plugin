# OpenSpec Review for Herdr

A focused, keyboard-and-mouse review pane for active [OpenSpec](https://openspec.dev/) changes, built as a plugin for the [Herdr](https://herdr.dev/) terminal workspace manager. It keeps proposal, spec, design, and task review one split away from the coding agents doing the work — no context switch, no browser.

![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)

> Requires [Herdr](https://herdr.dev/) 0.8+ and the [OpenSpec](https://openspec.dev/) CLI. Pure Python — no packages to install (the Markdown parser is vendored in-tree).

## Why

If you drive development with OpenSpec, your changes live as Markdown under `openspec/` and your agents work in terminal panes. This plugin puts a live review pane beside them: it lists every active change, shows each one's state and task progress at a glance, renders the artifacts as real Markdown, and — inside Herdr — can hand a change's next step straight to the agent in the pane next door.

## Requirements

- **Herdr** 0.8 or newer (`herdr --version`)
- **OpenSpec** CLI on your `PATH` (`openspec`)
- **Python 3.9+** (standard library only)
- **macOS or Linux**
- Optional: the `code` CLI, for opening a change folder in VS Code with `e`

## Install

Clone the repo and link it as a Herdr plugin:

```sh
git clone https://github.com/agerauer/herdr-openspec-plugin.git
cd herdr-openspec-plugin
herdr plugin link .
```

Then open the review pane from any Herdr workspace:

```sh
herdr plugin action invoke herdr.openspec-review.open-sidebar
```

The action reads the invoking pane's foreground directory, resolves the Git workspace (or the highest ancestor containing an `openspec/` directory), and opens the review pane on the right at about half the width — resize it however you like. Invoking it again focuses the existing pane for that workspace.

### Bind a key (recommended)

Add a binding to `~/.config/herdr/config.toml`:

```toml
[[keys.command]]
key = "prefix+o"
type = "plugin_action"
command = "herdr.openspec-review.open-sidebar"
description = "Open OpenSpec review"
```

Then reload: `herdr server reload-config`.

## What you get

- **Every active change as a card** — bold name, a `STATE · done/total · N Artifacts` line, and the description — for all changes at once, not just a selected one. Cards fill the pane height and the selection always stays in view.
- **A state derived from progress and validity**, color-coded and prominent: `DRAFT` (no tasks yet, or a required artifact missing), `READY` (`0/Y`), `IN PROGRESS` (`X/Y`), `DONE` (`Y/Y`), or `INVALID` (validation failed).
- **Markdown-rendered artifacts** — color-coded headings, **bold**, *italic*, inline and fenced code, links, nested and ordered lists with hanging indents, and pipe tables that shrink to fit the pane.
- **A tabbed document viewer** — the standard artifacts (Proposal, Design, Tasks), any other `.md` documents in the change folder, and one tab per spec, each color-coded by group. The tab bar wraps as needed and the change name heads the view.
- **Multi-root discovery** — changes from the workspace `openspec/` tree and from OpenSpec directories up to two levels below it (e.g. `apps/api/openspec`). Nested changes are prefixed with their project path (`api · add-login`).
- **Worktree-aware ordering** — in a Git workspace, changes touched on your branch are grouped at the top in an accent color, and the most likely one is selected first (details below).
- **On-demand validation** — press `v` to run `openspec validate` in the change's own project.
- **Send the next action to your agent** — inside Herdr, a one-click hand-off to the coding agent in the pane to the left (see below).

## Send the next action to your agent

When the pane runs inside Herdr, each actionable card shows its single next step as a button on the status line, and the `a` key does the same for the selected change:

| Card state | Button | What it sends to the agent on the left |
| --- | --- | --- |
| `READY` | `apply` | `/opsx:apply <change>` |
| `IN PROGRESS` | `investigate` | a prompt asking it to look at the change's open tasks |
| `DONE` | `archive` | `/opsx:archive <change>` |
| `DRAFT` / `INVALID` | — | nothing |

The plugin resolves the pane immediately to its left, confirms it's a coding agent that isn't mid-prompt, submits the instruction, and focuses it so you can watch and respond. If there's no such pane — or it's busy — it tells you why nothing was sent. Outside Herdr there's no button.

> This hand-off targets a [Claude Code](https://claude.com/claude-code) agent running in the neighbouring pane and uses its `/opsx:*` workflow commands. Other panes are detected and reported rather than sent to.

## Controls

| Input | Action |
| --- | --- |
| `↑` / `↓`, `j` / `k` | Move the change selection; scroll an open document by one wrapped line |
| `Page Up` / `Page Down` | Scroll an open document by one visible page |
| `→`, `l` | Open the selected change's Proposal; in the viewer, move to the next tab or spec |
| `←`, `h` | In the viewer, move to the previous tab, or return if Proposal is open |
| `Esc` | Return from a document to the main view |
| `Enter` | Open the selected change's Proposal |
| `p`, `d`, `t` | Open Proposal, Design, or Tasks (from the list or the viewer) |
| `s` | Open the first specification; in the viewer, rotate through specs |
| `a` | Send the selected change's next action to the agent in the pane to the left (inside Herdr, when actionable) |
| `v` | Validate the selected change with OpenSpec |
| `e` | Open the selected change's folder in VS Code (needs `code` on `PATH`) |
| `r` | Refresh now (the pane also watches for changes) |
| `m` | Toggle the pane's mouse capture — off to select/copy text with the terminal, on for in-pane clicks and wheel scrolling |
| `q` | Close the review pane |
| Left-click a change card | Select that change |
| Left-click a card's action button | Select the change and send its next action to the agent on the left |
| Left-click a viewer tab | Switch to that artifact |
| Left-click the viewer's back label | Return to the main view |
| Left-click a footer hint | Run the shown action |
| Mouse wheel | Scroll an open document one wrapped line per event |

## How worktree ordering works

In a Git workspace, the sidebar compares every discovered `openspec/changes/` tree against the merge base of the repository's default branch — including committed branch differences, staged and unstaged edits, and untracked files. Touched changes sort above untouched ones, in an accent color, whichever OpenSpec root they came from.

Within the touched group, a change whose folder name matches the branch or worktree name ranks first, then partial name matches, then most recent activity. The top-ranked touched change is selected when the pane opens; refreshes keep your current selection while it still exists.

The base is resolved from the remote default branch, then `origin/main`, local `main`, `origin/master`, and local `master`. If the project isn't a Git worktree, or Git inspection fails or times out, the pane still opens with plain alphabetical ordering and no worktree markers.

## Development

The plugin is a single-file curses app (`sidebar.py`) plus a small launcher (`scripts/open_sidebar.py`). It has **no runtime dependencies** — the [mistune](https://github.com/lepture/mistune) Markdown parser is vendored under `vendor/` so `python3 sidebar.py` runs against the standard library alone.

Run the tests:

```sh
python3 -m unittest discover -s tests -v
```

## License

Released under the [MIT License](LICENSE).

Bundled third-party code under `vendor/` keeps its own license: **mistune** (BSD-3-Clause), noted in [`vendor/README.md`](vendor/README.md).
