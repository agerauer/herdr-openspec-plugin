## Why

The document viewer flattens Markdown into gray body text: `clean_markdown` strips `**bold**`, inline `` `code` ``, and links to their plain text, uppercases headings, and discards fenced-code and table structure. The only styling that reaches the screen is a bold attribute applied to whole heading lines because they happen to be uppercase. Reviewers read proposals, designs, specs, and tasks in this pane all day, and the formatting that makes those documents scannable — emphasis, lists, code, tables, distinct headings — is exactly what the viewer throws away.

## What Changes

- Replace the plain-string rendering pipeline (`clean_markdown` → `wrap_document` → whole-line `put`) with a **styled-line model**: each visual line becomes a sequence of `(text, attr)` spans, drawn span-by-span so styling can vary *within* a line.
- Render **headings** in color by level and stop force-uppercasing them; keep an underline rule.
- Render **bold**, **italic**, and **inline code** as real terminal attributes, and keep **links** readable (styled text, URL dropped) instead of stripping markers.
- Render **lists** with bullet/number markers, nesting by indent depth, and a hanging indent so wrapped continuation lines align under the item text rather than the margin.
- Render **fenced code blocks** in a distinct style without reflowing them (whitespace preserved; no syntax highlighting).
- Render **GFM tables** as an aligned grid; when a table is wider than the pane, proportionally shrink columns and wrap cell text so no data is lost.
- Vendor a small pure-Python Markdown parser (mistune) into the repository so parsing is not hand-rolled, while the AST-to-curses rendering stays in this codebase. No install-time or runtime dependency is added to the plugin's launch (`python3 sidebar.py`).
- Preserve the existing scroll, percentage, clamp, and hit-testing behavior: one styled line remains exactly one wrapped visual line, so `sidebar-navigation`'s "wrapped visual line" scrolling contract is unchanged.

## Capabilities

### New Capabilities
- `document-viewer-markdown`: How the document viewer renders Markdown content — styled inline spans (bold, italic, inline code, links), colored headings, structured lists, fenced code blocks, and tables — into the terminal pane, including how content wider than the pane is fit.

### Modified Capabilities
<!-- None. Existing specs cover scrolling and navigation, not content rendering. A styled line stays one wrapped visual line, so sidebar-navigation's scrolling requirements continue to hold unchanged. -->

## Impact

- **Code**: `sidebar.py` — `clean_markdown` and `wrap_document` are replaced by a span-producing renderer; the viewer draw loop (`draw_viewer`) walks spans advancing `x` instead of one `put` per line. New pure helpers for span-aware word wrapping and table layout.
- **Dependencies**: adds a vendored `mistune` package (pure Python, MIT) committed to the repository. No change to how the plugin is launched or installed; the README's zero-install-dependency promise is preserved (third-party source lives in the tree, with its license retained).
- **Tests**: `tests/test_sidebar.py` — the single assertion on `wrap_document`'s `list[str]` contract is updated for the styled-line return type; new unit tests cover span emission, wrapping, and table fitting. Scroll/offset/hit-test tests are unaffected because line counts and geometry are preserved.
- **Docs**: `README.md` — note that the viewer renders formatted Markdown.
- **Out of scope**: syntax highlighting of code blocks, and any alternative table-overflow mode beyond shrink-and-wrap.
