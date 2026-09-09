## Purpose

Define how the document viewer renders Markdown content — emphasis, code, headings, lists, and tables — into the review pane so proposals, designs, specs, and tasks are as scannable on screen as in their source files.

## ADDED Requirements

### Requirement: Inline emphasis and code render as distinct styles

Within a rendered line, the viewer SHALL display bold, italic, and inline code with visually distinct terminal styling rather than showing or discarding their Markdown markers. Different styles MAY apply to different portions of the same line. Link text SHALL be displayed as readable styled text with its Markdown link syntax removed. When the terminal cannot express a style (for example, italic), the viewer SHALL substitute another visible style rather than fall back to unstyled text or leave raw markers.

#### Scenario: A line mixes plain, bold, and code text

- **WHEN** a paragraph line contains plain text, a `**bold**` span, and an inline `` `code` `` span
- **THEN** the plain text, the bold text, and the code text each render with their own styling on the same line, and no `*` or `` ` `` markers appear

#### Scenario: A link is rendered

- **WHEN** a line contains a `[label](url)` link
- **THEN** the viewer displays `label` as styled text and does not display the surrounding brackets, parentheses, or URL

#### Scenario: Italic is unsupported by the terminal

- **WHEN** a line contains italic text and the terminal does not render an italic attribute
- **THEN** the viewer renders that text with an alternative visible style and shows no `*` or `_` markers

### Requirement: Headings render in color by level

The viewer SHALL render Markdown headings in a color determined by heading level and SHALL preserve the heading's original letter case. A visual separator MAY follow a heading.

#### Scenario: Headings of different levels are shown

- **WHEN** the document contains headings of different levels
- **THEN** each heading is displayed in the color assigned to its level, in its original case, without being converted to uppercase

### Requirement: Lists render with markers, nesting, and hanging indent

The viewer SHALL render unordered list items with a bullet marker and ordered list items with their number, SHALL indent nested items according to their depth, and SHALL align the wrapped continuation lines of an item under the item's text rather than under its marker.

#### Scenario: A long list item wraps

- **WHEN** an unordered list item is too long to fit on one line
- **THEN** the first line begins with the bullet marker and each continuation line is indented to align beneath the item text, not beneath the marker

#### Scenario: A nested list is shown

- **WHEN** a list contains items nested beneath other items
- **THEN** the nested items are indented further than their parent items and carry their own markers

### Requirement: Fenced code blocks render verbatim in a distinct style

The viewer SHALL render fenced code blocks in a style distinct from body text and SHALL preserve their internal whitespace and line breaks without reflowing the code to the pane width.

#### Scenario: A fenced code block is shown

- **WHEN** the document contains a fenced code block
- **THEN** its lines are displayed in the code style with original indentation and line breaks preserved, and its opening and closing fence markers are not displayed as content

### Requirement: Tables render as an aligned grid that fits the pane

The viewer SHALL render GFM tables as a column-aligned grid with a visible separation between header and body. When a table's natural width exceeds the available pane width, the viewer SHALL reduce column widths and wrap cell text across multiple lines so that the whole table fits within the pane and no cell content is discarded.

#### Scenario: A table fits the pane

- **WHEN** the document contains a table narrower than the pane
- **THEN** the table renders as an aligned grid with its columns lined up and its header separated from its body

#### Scenario: A table is wider than the pane

- **WHEN** the document contains a table whose natural width exceeds the pane width
- **THEN** the viewer narrows the columns and wraps cell text onto additional lines so the table fits the pane width and every cell's text remains present

### Requirement: Rendered content stays within the pane and preserves scroll geometry

Each rendered visual line SHALL occupy exactly one scrollable row and SHALL NOT extend beyond the right edge of the pane. Line-by-line and page scrolling, the scroll-position indicator, and boundary clamping SHALL continue to operate over the rendered lines.

#### Scenario: A styled line reaches the pane edge

- **WHEN** a rendered line's styled content would exceed the pane width
- **THEN** the line is wrapped or clipped so it does not draw past the right edge, and it still counts as a single scrollable row

#### Scenario: The reader scrolls a rendered document

- **WHEN** the reader scrolls the document by line or by page
- **THEN** the offset moves over the rendered visual lines and stops at the first and last available rows
