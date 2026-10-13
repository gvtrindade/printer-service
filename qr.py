"""QR code rendering helpers."""
import base64
import io

import qrcode
from qrcode.constants import ERROR_CORRECT_M


def make_qr_data_uri(payload: str) -> str:
    """Render ``payload`` as a QR code and return a PNG data URI.

    The result can be dropped straight into an SVG ``<image href="...">``.
    """
    qr = qrcode.QRCode(
        version=None,
        error_correction=ERROR_CORRECT_M,
        box_size=10,
        border=1,
    )
    qr.add_data(payload)
    qr.make(fit=True)

    image = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"
