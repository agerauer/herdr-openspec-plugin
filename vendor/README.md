# Vendored third-party code

Committed here to keep the plugin's `python3 sidebar.py` launch dependency-free.

- **mistune 3.3.4** — pure-Python Markdown parser (BSD-3-Clause). Source:
  https://pypi.org/project/mistune/3.3.4/ , extracted from the official wheel.
  License retained at `mistune/LICENSE`. Used in AST mode only
  (`mistune.create_markdown(renderer=None)`).

To update: download the wheel, extract the `mistune/` package here, refresh
this note and the pinned version.
