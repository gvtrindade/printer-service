from templating import validate_template, populate

SAMPLE_SVG = (
    "<svg>"
    "<text>{{title}}</text>"
    "<text>{{price}}</text>"
    '<image xlink:href="{{qr}}"/>'
    "</svg>"
)

TITLE_TEMPLATE = (
    '<svg viewBox="0 0 40 25">'
    '<text xml:space="preserve" '
    'style="font-size:3.2px;writing-mode:lr-tb;fill:#000000;stroke:#000000;stroke-width:0.27" '
    'x="14" y="6" id="text2"><tspan id="tspan2" style="stroke-width:0.27" '
    'x="14" y="6">{{title}}</tspan></text>'
    "</svg>"
)


def test_validate_template_no_unknown():
    assert validate_template(SAMPLE_SVG) == []


def test_validate_template_unknown_fields():
    svg = '<svg><text>{{title}}</text><text>{{unknown}}</text></svg>'
    assert validate_template(svg) == ["unknown"]


def test_validate_template_multiple_unknown():
    svg = '<svg><text>{{foo}}</text><text>{{bar}}</text></svg>'
    assert validate_template(svg) == ["bar", "foo"]


def test_populate_basic():
    product = {"title": "Dune", "price": "12.99", "qr": "data:image/png;base64,AAAA"}
    result = populate(SAMPLE_SVG, product)
    assert "<text>Dune</text>" in result
    assert "<text>12.99</text>" in result
    assert 'xlink:href="data:image/png;base64,AAAA"' in result


def test_qr_placeholder_in_text_becomes_image():
    svg = (
        '<svg viewBox="0 0 40 25">'
        '<text x="3.4" y="19.85" style="font-size:4.2px">'
        '<tspan x="3.4" y="19.85">{{qr}}</tspan></text>'
        "</svg>"
    )
    product = {"qr": "data:image/png;base64,AAAA"}
    result = populate(svg, product)
    assert "<text" not in result
    assert '<image x="3.4" y="9.6" width="10.25" height="10.25"' in result
    assert 'href="data:image/png;base64,AAAA"' in result


def test_qr_placeholder_in_image_is_untouched():
    svg = '<svg><image xlink:href="{{qr}}"/></svg>'
    result = populate(svg, {"qr": "data:image/png;base64,AAAA"})
    assert result == svg.replace("{{qr}}", "data:image/png;base64,AAAA")


def test_qr_in_text_keeps_other_text_placeholders():
    svg = '<svg><text>{{title}}</text><text x="2" y="20">{{qr}}</text></svg>'
    result = populate(svg, {"title": "Dune", "qr": "data:image/png;base64,AAAA"})
    assert "<text>Dune</text>" in result
    assert "<image" in result
    assert "data:image/png;base64,AAAA" in result


def test_populate_escapes_xml():
    product = {"title": "A & B <C>", "price": "5", "qr": ""}
    result = populate(SAMPLE_SVG, product)
    assert "A &amp; B &lt;C&gt;" in result


def test_populate_missing_field_empty():
    product = {"title": "Dune"}
    result = populate(SAMPLE_SVG, product)
    assert "<text></text>" in result


def test_populate_handles_whitespace_in_placeholder():
    svg = "<svg><text>{{ title }}</text></svg>"
    product = {"title": "Dune"}
    result = populate(svg, product)
    assert "<text>Dune</text>" in result


def test_title_short_stays_single_line():
    result = populate(TITLE_TEMPLATE, {"title": "Dune"})
    assert result.count("<tspan") == 1
    assert ">Dune</tspan>" in result
    assert "font-size:3.2" in result


def test_title_wraps_when_long():
    result = populate(TITLE_TEMPLATE, {"title": "The Hitchhiker's Guide to the Galaxy"})
    assert result.count("<tspan") > 1


def test_title_shrinks_for_very_long_titles():
    short = populate(TITLE_TEMPLATE, {"title": "Dune"})
    long = populate(
        TITLE_TEMPLATE,
        {"title": "An Extremely Long Product Title That Cannot Possibly Fit"},
    )

    def font_size(svg: str) -> float:
        import re

        return float(re.search(r"font-size:([\d.]+)", svg).group(1))

    assert font_size(long) < font_size(short)


def test_title_tspans_are_offset_vertically():
    result = populate(TITLE_TEMPLATE, {"title": "The Hitchhiker's Guide to the Galaxy"})
    import re

    ys = [float(y) for y in re.findall(r"<tspan[^>]*y=\"([\d.]+)\"", result)]
    assert len(ys) > 1
    assert ys == sorted(ys)
    assert ys[0] < ys[1]
