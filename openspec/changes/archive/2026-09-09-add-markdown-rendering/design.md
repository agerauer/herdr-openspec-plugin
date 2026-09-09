## Context

See proposal.md — Why. Today the viewer runs `clean_markdown(md) -> list[str]` then `wrap_document` (a `textwrap.wrap` per line), and draws each line with a single `self.put(row, x, text, attr)` — one curses attribute per whole line. `self.put` is `screen.addnstr(...)`; curses draws through its own attribute model and cannot interpret ANSI escape codes, so any renderer that emits ANSI to a stream (rich, glow, bat, mdcat) does not compose with this pane. The plugin launches as `python3 sidebar.py` against the user's system Python with no venv, no `requirements.txt`, and no install step; the README advertises a zero-dependency install. Scroll offset, the `%` indicator, `clamp_document_offset`, and click hit-testing all currently assume `len(str) == columns`.

## Goals / Non-Goals

**Goals:**
- A rendering path that can style parts of a line and color headings while staying inside the curses pane.
- Keep parsing off our hands (no hand-rolled Markdown grammar) without adding an install- or runtime-time dependency.
- Preserve exact scroll/geometry behavior: one rendered line == one wrapped visual row.
- Keep the render path pure and unit-testable, as `clean_markdown`/`wrap_document` are today.

**Non-Goals:**
- Syntax highlighting of code blocks (would pull in pygments and break the zero-dependency posture).
- Table-overflow modes other than shrink-and-wrap (record view, truncate, horizontal scroll are explicitly excluded).
- East-Asian / emoji wide-character width correctness beyond a documented `len()`-based approximation.

## Decisions

### Decision: Styled-line span model replaces plain strings

A rendered document becomes `list[StyledLine]` where `StyledLine = list[Span]` and `Span = (text: str, attr: int)`. The draw loop walks spans, drawing each with `self.put(row, x, span.text, span.attr)` and advancing `x` by the span's visible width, clipping cumulatively at the pane edge. Because each `StyledLine` is still exactly one wrapped visual row, `clamp_document_offset`, the `%` math, and scroll offsets keep working unchanged.

- **Why:** `addnstr` applies one attribute per call; sub-line styling and colored headings are impossible with a `list[str]`. Spans are the minimal model that carries per-run attributes while keeping the one-line-per-row invariant the scroll code depends on.
- **Alternatives:** Keep `list[str]` and encode a parallel attribute mask per character — more memory and bookkeeping than spans for no gain. Emit ANSI into a curses pad — rejected: pads store cells+attributes, not escape bytes, so it would require an ANSI-to-attribute translator.

### Decision: Vendor mistune for parsing; write the AST-to-span visitor ourselves

Vendor mistune (v3, pure Python, MIT — a handful of `.py` files) into the repository and use its AST mode (`create_markdown(renderer=None)`), which yields a nested-dict tree. A visitor walks blocks and inline nodes and emits `StyledLine`s. The visitor is intrinsic to this app — it maps nodes to *our* color pairs and draws through *our* `self.put` — so no library can supply it.

- **Why:** Parsing (nested emphasis, the `*` bold/italic/bullet ambiguity, list nesting, fenced-code state, table cells) is the error-prone part and the reason not to hand-roll. Vendoring keeps the launch command dependency-free while still not owning a grammar. mistune's nested AST suits a recursive visitor better than markdown-it-py's flat open/close token stream.
- **Alternatives:** `pip install` a parser — rejected: no dependency mechanism exists and it breaks the zero-install promise. Rewrite on Textual (real Markdown widget) — rejected: rewrites the whole curses app and adds a heavy async dependency tree. Shell out to glow/bat by suspending curses — rejected here: full fidelity but a mode switch out of the integrated pane and an external-binary requirement.

### Decision: Span-aware word wrap is the one new primitive

A helper `wrap_spans(spans, width, subsequent_indent) -> list[StyledLine]` walks words across spans, tracks *visible* columns (not the length of styled text), breaks at `width`, carries each word's attribute, and applies a hanging indent to continuation lines. Paragraphs and list items wrap through it; fenced code and table cells use dedicated paths.

- **Why:** `textwrap.wrap` operates on plain strings and cannot preserve spans or hanging indents. This ~30-line pure function is what makes lists hang correctly and keeps bold/italic intact across a line break.

### Decision: Style map and inline attribute composition

Heading level → color pair (reusing the existing pairs 1–4: cyan/green/yellow/red, mapped by level). Bold → `A_BOLD`; italic → `A_ITALIC` with a fallback to `A_UNDERLINE` when the terminal lacks italic; inline code → a code color/attribute; link → underline plus color. Nested inline nodes OR their attributes together as the visitor descends (a bold link is `A_BOLD | A_UNDERLINE | color`).

- **Why:** Colors already exist in `init_pair`; OR-composition matches how curses attributes combine and handles nesting without special cases.

### Decision: Tables shrink-and-wrap to fit

Parse tables via mistune's table plugin (structured rows/cells). Compute natural column widths from content; if their sum plus borders exceeds pane width, reduce columns proportionally (widest first, down to a floor) and wrap each cell with `wrap_spans`, expanding a row to the height of its tallest cell. Render header, a separator, then body.

- **Why:** Chosen overflow policy (see proposal) keeps the grid and loses no data in a narrow docked pane. Truncation hides data; a record view abandons the grid; horizontal scroll adds new interaction state.

## Risks / Trade-offs

- **Vendored third-party code in the tree** → keep mistune's LICENSE alongside it and pin the vendored version; `.gitignore` only excludes `__pycache__`/`*.pyc`, so it commits cleanly.
- **`len()` mis-measures wide/zero-width characters**, drifting wrap and table math → acceptable for these mostly-ASCII documents; documented as a Non-Goal and isolated in one width helper so it can be upgraded later.
- **Dense tables become tall** under shrink-and-wrap → accepted trade-off of the chosen policy; the pane scrolls.
- **Terminal attribute support varies** (italic especially) → the style map defines fallbacks so text is never left as raw markers.
- **Rendering is now per-width** (wrapping and table layout depend on pane width) → recompute on resize like the current `wrap_document` already does; keep the renderer pure so results are cacheable by `(content, width)` if profiling warrants.

## Migration Plan

Replace `clean_markdown`/`wrap_document` with the new renderer and update `draw_viewer` to walk spans; keep the function seam so the change is internal to `sidebar.py` plus the vendored package. Update the single `wrap_document` contract test to the styled-line return type and add unit tests for span emission, `wrap_spans`, and table fitting. No user-facing controls change, so there is no rollback beyond reverting the change.

## Open Questions

- Exact heading-level → color assignment and the inline code color are presentation details to settle during implementation; they do not affect the specs, the approach, or the task breakdown.
