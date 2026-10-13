import base64

from qr import make_qr_data_uri


def test_make_qr_data_uri_is_png_data_uri():
    uri = make_qr_data_uri("E:12345")
    assert uri.startswith("data:image/png;base64,")
    raw = base64.b64decode(uri.split(",", 1)[1])
    assert raw.startswith(b"\x89PNG\r\n\x1a\n")
