import re
from xml.sax.saxutils import escape

PLACEHOLDER_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")
ALLOWED_FIELDS = {"id", "title", "price", "qr", "e_id"}

# Matches a full <text ...>...</text> element.
_TEXT_BLOCK_RE = re.compile(r"<text\b[^>]*>.*?</text>", re.DOTALL)
_OPEN_TAG_RE = re.compile(r"<text\b[^>]*>", re.DOTALL)
_TSPAN_TAG_RE = re.compile(r"<tspan\b[^>]*>", re.DOTALL)
_FONT_SIZE_RE = re.compile(r"font-size:\s*([\d.]+)")
_STROKE_WIDTH_RE = re.compile(r"stroke-width:\s*([\d.]+)")
_X_ATTR_RE = re.compile(r'\bx="([-\d.]+)"')
_Y_ATTR_RE = re.compile(r'\by="([-\d.]+)"')
_VIEWBOX_RE = re.compile(r'viewBox\s*=\s*"[\d.\s-]*?([\d.]+)\s+([\d.]+)"')
_WIDTH_RE = re.compile(r'width\s*=\s*"([\d.]+)')

# Approximate average glyph advance for the label's sans-serif font, as a
# fraction of the font size. Used to estimate how much text fits per line.
CHAR_WIDTH_RATIO = 0.58
# Vertical distance between wrapped lines, as a multiple of the font size.
LINE_HEIGHT_RATIO = 1.15
# Never shrink the title below this size (SVG user units).
MIN_TITLE_FONT_SIZE = 1.4
# Keep this much space to the right of the title.
TITLE_RIGHT_MARGIN = 0.6
# Maximum number of wrapped title lines before the font is shrunk.
TITLE_MAX_LINES = 3
# Side length (SVG user units) of the square image generated when a template
# puts the {{qr}} placeholder inside a <text> element.
QR_IMAGE_SIZE = 10.25


def validate_template(svg_template: str) -> list[str]:
    unknown = sorted(set(PLACEHOLDER_RE.findall(svg_template)) - ALLOWED_FIELDS)
    return unknown


def populate(svg_template: str, product: dict) -> str:
    svg = _render_title(svg_template, str(product.get("title", "")))

    qr_value = str(product.get("qr", ""))
    if qr_value:
        svg = _render_qr(svg, qr_value)

    def _replace(m: re.Match) -> str:
        field = m.group(1)
        value = str(product.get(field, ""))
        return escape(value)

    return PLACEHOLDER_RE.sub(_replace, svg)


def _render_qr(svg: str, qr_data_uri: str) -> str:
    """Replace <text> elements holding {{qr}} with a square <image>.

    A bitmap cannot be drawn inside a <text> element, so a template that puts
    the {{qr}} placeholder in text would otherwise print the raw data URI. The
    generated image is anchored at the text baseline, so it sits where the
    placeholder used to be.
    """

    def _repl(m: re.Match) -> str:
        block = m.group(0)
        if "qr" not in PLACEHOLDER_RE.findall(block):
            return block

        open_tag_match = _OPEN_TAG_RE.match(block)
        open_tag = open_tag_match.group(0) if open_tag_match else "<text>"
        tspan_match = _TSPAN_TAG_RE.search(block)
        geometry_source = tspan_match.group(0) if tspan_match else open_tag
        x = _attr(_X_ATTR_RE, geometry_source)
        y = _attr(_Y_ATTR_RE, geometry_source)
        if x is None:
            x = 0.0
        if y is None:
            y = QR_IMAGE_SIZE
        top = max(0.0, y - QR_IMAGE_SIZE)
        # ``href`` (SVG 2) is used instead of ``xlink:href`` so templates
        # without an ``xmlns:xlink`` declaration keep working.
        return (
            f'<image x="{x:g}" y="{top:g}" width="{QR_IMAGE_SIZE:g}" '
            f'height="{QR_IMAGE_SIZE:g}" preserveAspectRatio="xMidYMid meet" '
            f'href="{escape(qr_data_uri)}"/>'
        )

    return _TEXT_BLOCK_RE.sub(_repl, svg)


def _render_title(svg: str, title: str) -> str:
    """Replace {{title}} with wrapped, size-adapted text."""

    def _repl(m: re.Match) -> str:
        block = m.group(0)
        fields = PLACEHOLDER_RE.findall(block)
        if "title" not in fields:
            return block
        return _rewrite_title_block(block, title, _svg_width(svg))

    return _TEXT_BLOCK_RE.sub(_repl, svg)


def _rewrite_title_block(block: str, title: str, svg_width: float) -> str:
    open_tag_match = _OPEN_TAG_RE.match(block)
    open_tag = open_tag_match.group(0) if open_tag_match else "<text>"

    font_size = _font_size(open_tag)
    tspan_match = _TSPAN_TAG_RE.search(block)
    geometry_source = tspan_match.group(0) if tspan_match else open_tag
    x = _attr(_X_ATTR_RE, geometry_source)
    y = _attr(_Y_ATTR_RE, geometry_source)

    # Template without usable geometry: fall back to a plain text replacement.
    if font_size is None or x is None or y is None:
        return re.sub(
            r"\{\{\s*title\s*\}\}", lambda _: escape(title), block
        )

    stroke_width = _attr(_STROKE_WIDTH_RE, geometry_source)
    if stroke_width is None:
        stroke_width = _attr(_STROKE_WIDTH_RE, open_tag)

    max_width = svg_width - x - TITLE_RIGHT_MARGIN
    font_size, lines = _fit_title(title, font_size, max_width)

    new_open_tag = re.sub(r"font-size:\s*[\d.]+", f"font-size:{font_size:g}", open_tag)
    line_height = font_size * LINE_HEIGHT_RATIO
    stroke = f' style="stroke-width:{stroke_width:g}"' if stroke_width is not None else ""
    tspans = "".join(
        f'<tspan{stroke} x="{x:g}" y="{y + i * line_height:g}">{escape(line)}</tspan>'
        for i, line in enumerate(lines)
    )
    return f"{new_open_tag}{tspans}</text>"


def _fit_title(
    title: str, base_font_size: float, max_width: float
) -> tuple[float, list[str]]:
    """Shrink the font until the title wraps into at most TITLE_MAX_LINES."""
    font_size = base_font_size
    while font_size >= MIN_TITLE_FONT_SIZE:
        lines = _wrap(title, font_size, max_width)
        if len(lines) <= TITLE_MAX_LINES:
            return font_size, lines
        font_size *= 0.9
    return MIN_TITLE_FONT_SIZE, _wrap(title, MIN_TITLE_FONT_SIZE, max_width)


def _wrap(text: str, font_size: float, max_width: float) -> list[str]:
    """Greedy word wrap using an estimated character width."""
    max_chars = max(1, int(max_width / (font_size * CHAR_WIDTH_RATIO)))
    lines: list[str] = []
    current = ""
    for word in text.split():
        candidate = f"{current} {word}".strip()
        if len(candidate) <= max_chars or not current:
            current = candidate
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines or [""]


def _font_size(tag: str) -> float | None:
    match = _FONT_SIZE_RE.search(tag)
    return float(match.group(1)) if match else None


def _attr(pattern: re.Pattern, tag: str) -> float | None:
    match = pattern.search(tag)
    return float(match.group(1)) if match else None


def _svg_width(svg: str) -> float:
    viewbox = _VIEWBOX_RE.search(svg)
    if viewbox:
        return float(viewbox.group(1))
    width = _WIDTH_RE.search(svg)
    if width:
        return float(width.group(1))
    return 40.0
