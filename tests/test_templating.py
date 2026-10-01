from templating import validate_template, populate

SAMPLE_SVG = '<svg><text>{{title}}</text><text>{{author}}</text><text>{{price}}</text></svg>'


def test_validate_template_no_unknown():
    assert validate_template(SAMPLE_SVG) == []


def test_validate_template_unknown_fields():
    svg = '<svg><text>{{title}}</text><text>{{unknown}}</text></svg>'
    assert validate_template(svg) == ["unknown"]


def test_validate_template_multiple_unknown():
    svg = '<svg><text>{{foo}}</text><text>{{bar}}</text></svg>'
    assert validate_template(svg) == ["bar", "foo"]


def test_populate_basic():
    book = {"id": "1", "title": "Dune", "author": "Herbert", "price": "12.99"}
    result = populate(SAMPLE_SVG, book)
    assert "<text>Dune</text>" in result
    assert "<text>Herbert</text>" in result
    assert "<text>12.99</text>" in result


def test_populate_escapes_xml():
    book = {"id": "1", "title": "A & B <C>", "author": "O'Brien", "price": "5"}
    result = populate(SAMPLE_SVG, book)
    assert "A &amp; B &lt;C&gt;" in result
    assert "O'Brien" in result


def test_populate_missing_field_empty():
    book = {"id": "1", "title": "Dune"}
    result = populate(SAMPLE_SVG, book)
    assert "<text></text>" in result


def test_populate_handles_whitespace_in_placeholder():
    svg = '<svg><text>{{ title }}</text></svg>'
    book = {"title": "Dune"}
    result = populate(svg, book)
    assert "<text>Dune</text>" in result
