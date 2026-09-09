## 1. Vendor the parser

- [x] 1.1 Vendor mistune (v3, pure Python) into the repository (e.g. `vendor/mistune/`) with its LICENSE and a note recording the pinned version; verify `python3 -c "import sys; sys.path.insert(0, 'vendor'); import mistune; print(mistune.__version__)"` runs with no network or site-packages install
- [x] 1.2 Add the vendored path to `sidebar.py`'s import resolution and expose a module-level `create_markdown(renderer=None)` AST parser; verify a unit test parses `"# H\n\ntext"` into a heading node followed by a paragraph node

## 2. Styled-line primitives

- [x] 2.1 Define `Span = (text, attr)` and `StyledLine = list[Span]`, plus a `visible_width(text)` helper; verify unit tests over ASCII strings return `len`-based widths and the types are used by later helpers
- [x] 2.2 Implement `wrap_spans(spans, width, subsequent_indent) -> list[StyledLine]` that breaks on visible columns, preserves each word's attr, and hanging-indents continuation lines; verify unit tests for: a bold word surviving a line break, and a wrapped item whose continuation is indented under the text

## 3. Style map and inline rendering

- [x] 3.1 Add a style map: heading level → color pair (reuse pairs 1–4), bold → `A_BOLD`, italic → `A_ITALIC` with `A_UNDERLINE` fallback when unsupported, inline code → code attr, link → underline+color; verify a unit test asserts italic resolves to the fallback attr when italic is reported unavailable
- [x] 3.2 Implement the inline visitor: walk `strong`/`emphasis`/`codespan`/`link`/`text` nodes into spans, OR-composing attrs while descending; verify a unit test renders `Use **bold** and `+"`code`"+` and `[l](u)` into the expected span sequence with no markers or URL

## 4. Block rendering

- [x] 4.1 Render headings (colored by level, original case, optional rule line) and paragraphs (via `wrap_spans`); verify unit tests assert heading color-by-level without uppercasing and a wrapped paragraph's line count
- [x] 4.2 Render lists: bullet/number markers, indent by nesting depth, hanging indent via `wrap_spans`; verify unit tests for a wrapped item's aligned continuation and a nested item's deeper indent
- [x] 4.3 Render fenced code blocks in the code style with whitespace and line breaks preserved and no reflow; verify a unit test that a multi-line block keeps its indentation and omits the fence markers

## 5. Table rendering

- [x] 5.1 Parse tables (mistune table plugin) and lay out columns at natural widths with a header/body separator; verify a unit test that a narrow table renders aligned columns
- [x] 5.2 When the table exceeds pane width, shrink columns proportionally (widest first, to a floor) and wrap cells with `wrap_spans`, expanding rows to the tallest cell; verify a unit test that a wide table fits the given width with no cell text dropped

## 6. Wire into the viewer

- [x] 6.1 Add `render_markdown(md, width) -> list[StyledLine]` that dispatches blocks to the renderers above and replaces `clean_markdown`/`wrap_document`; verify `render_markdown("one\ntwo\nthree", 40)` yields three single-span lines
- [x] 6.2 Update `draw_viewer` to walk each `StyledLine`, drawing spans with `self.put` and advancing `x`, clipping cumulatively at the pane edge; verify by manual run that a sample document shows colored headings, bold/italic/code, lists, a code block, and a table within the pane
- [x] 6.3 Confirm scroll geometry is preserved: line/page scroll, the `%` indicator, and `clamp_document_offset` operate over rendered lines; verify existing scroll/offset tests pass unchanged

## 7. Tests and docs

- [x] 7.1 Update the existing `wrap_document` contract test to the styled-line return type (or point it at `render_markdown`); verify `python3 -m unittest discover -s tests -v` passes
- [x] 7.2 Update `README.md` to state the viewer renders formatted Markdown (headings, emphasis, code, lists, tables); verify the README no longer implies plain-text rendering
