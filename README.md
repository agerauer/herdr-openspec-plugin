# OpenSpec Review for Herdr

A narrow, keyboard-first review pane for active [OpenSpec](https://openspec.dev/) changes. It keeps proposal, specification, design, and task review in the same terminal workspace as your coding agents.

## What it shows

- Every active change under `openspec/changes/`
- Missing and optional artifacts
- ADDED, MODIFIED, REMOVED, and RENAMED requirement counts
- Per-change `X/Y` task completion directly in every change-list row
- `openspec validate` results on demand

## Install for local development

Requirements: Herdr 0.8+, OpenSpec, and Python 3 on macOS or Linux.

```sh
herdr plugin link .
herdr plugin action invoke herdr.openspec-review.open-sidebar
```

The action uses the invoking pane's foreground directory, finds the nearest OpenSpec project, and opens the review pane on the right. The pane process stays rooted in the plugin checkout while the selected project is passed separately, so it works from any Herdr workspace. Invoking it again focuses the existing review pane for that workspace and project.

To bind it in `~/.config/herdr/config.toml`:

```toml
[[keys.command]]
key = "prefix+o"
type = "plugin_action"
command = "herdr.openspec-review.open-sidebar"
description = "Open OpenSpec review"
```

Then run `herdr server reload-config`.

## Keys

| Key | Action |
| --- | --- |
| `↑` / `↓`, `j` / `k` | Move selection or scroll a document |
| `Tab`, `←` / `→`, `h` / `l` | Move between changes and artifacts |
| `Enter` | Open the selected artifact |
| `v` | Validate the selected change with OpenSpec |
| `e` | Edit the open artifact with `$EDITOR` |
| `r` | Refresh now (the pane also watches for changes) |
| `q` | Close the review pane |

## Test

```sh
python3 -m unittest discover -s tests -v
```
