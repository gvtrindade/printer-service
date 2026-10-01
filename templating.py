import re
from xml.sax.saxutils import escape

PLACEHOLDER_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")
ALLOWED_FIELDS = {"id", "title", "author", "price"}


def validate_template(svg_template: str) -> list[str]:
    unknown = sorted(set(PLACEHOLDER_RE.findall(svg_template)) - ALLOWED_FIELDS)
    return unknown


def populate(svg_template: str, book: dict) -> str:
    def _replace(m: re.Match) -> str:
        field = m.group(1)
        value = str(book.get(field, ""))
        return escape(value)

    return PLACEHOLDER_RE.sub(_replace, svg_template)
