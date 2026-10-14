import errno
import io
import os

import cairosvg
import usb.core
import usb.util
from PIL import Image

USB_VENDOR = 0x0FE6
USB_PRODUCT = 0x8800
PRINTER_DPI = 203
LABEL_WIDTH_MM = 40
LABEL_HEIGHT_MM = 25
LABEL_WIDTH_PX = round(LABEL_WIDTH_MM / 25.4 * PRINTER_DPI)
LABEL_HEIGHT_PX = round(LABEL_HEIGHT_MM / 25.4 * PRINTER_DPI)

# Manual print registration (mm). The RP420 ignores ZPL label-home/top/shift
# commands, so the design is shifted inside the rendered bitmap instead.
# Positive X moves the design right, positive Y moves it down.
PRINT_OFFSET_X_MM = float(os.getenv("PRINT_OFFSET_X_MM", "0"))
PRINT_OFFSET_Y_MM = float(os.getenv("PRINT_OFFSET_Y_MM", "0"))

_INVERT = bytes(range(255, -1, -1))


class PrinterError(Exception):
    pass


class PrinterNotFoundError(PrinterError):
    pass


class UsbWriteError(PrinterError):
    pass


def open_printer():
    dev = usb.core.find(idVendor=USB_VENDOR, idProduct=USB_PRODUCT)
    if dev is None:
        raise PrinterNotFoundError("printer not found (USB 0fe6:8800)")
    try:
        if dev.is_kernel_driver_active(0):
            dev.detach_kernel_driver(0)
    except (usb.core.USBError, NotImplementedError):
        pass
    try:
        dev.set_configuration()
    except usb.core.USBError as e:
        # EBUSY means the device is already configured (e.g. still claimed
        # from a previous print) — the active configuration is usable.
        if e.errno != errno.EBUSY:
            raise
    cfg = dev.get_active_configuration()
    intf = cfg[(0, 0)]
    ep_out = usb.util.find_descriptor(
        intf,
        custom_match=lambda e: usb.util.endpoint_direction(e.bEndpointAddress)
        == usb.util.ENDPOINT_OUT,
    )
    if ep_out is None:
        raise PrinterNotFoundError("no bulk OUT endpoint found on printer")
    return dev, ep_out


def render_label(svg_text: str) -> bytes:
    png_data = cairosvg.svg2png(
        bytestring=svg_text.encode(),
        output_width=LABEL_WIDTH_PX,
        output_height=LABEL_HEIGHT_PX,
        background_color="white",
    )
    img = Image.open(io.BytesIO(png_data))
    img = img.convert("RGB").convert("1", dither=Image.Dither.FLOYDSTEINBERG)
    img = img.resize((LABEL_WIDTH_PX, LABEL_HEIGHT_PX), Image.Resampling.LANCZOS)

    offset_x = round(PRINT_OFFSET_X_MM / 25.4 * PRINTER_DPI)
    offset_y = round(PRINT_OFFSET_Y_MM / 25.4 * PRINTER_DPI)
    if offset_x or offset_y:
        canvas = Image.new("1", (LABEL_WIDTH_PX, LABEL_HEIGHT_PX), 1)
        canvas.paste(img, (offset_x, offset_y))
        img = canvas

    width_bytes = (img.width + 7) // 8
    data = img.tobytes().translate(_INVERT)
    total_bytes = width_bytes * img.height
    hex_data = data.hex().upper()

    return (
        "^XA\r\n"
        # Reset any stored registration so the graphic lands exactly on the
        # label instead of inheriting a saved label-home/top/shift offset.
        "^LH0,0\r\n"
        "^LT0\r\n"
        "^LS0\r\n"
        "^MNY\r\n"
        f"^PW{LABEL_WIDTH_PX}\r\n"
        f"^LL{LABEL_HEIGHT_PX}\r\n"
        "^FO0,0\r\n"
        f"^GFA,{total_bytes},{total_bytes},{width_bytes},{hex_data}\r\n"
        "^FS\r\n"
        "^PQ1\r\n"
        "^XZ\r\n"
    ).encode()


def send_to_printer(zpl: bytes) -> None:
    dev, ep_out = open_printer()
    try:
        dev.write(ep_out.bEndpointAddress, zpl, timeout=60000)
    except usb.core.USBError as e:
        raise UsbWriteError(f"USB write failed: {e}") from e
    finally:
        usb.util.dispose_resources(dev)


def printer_is_available() -> bool:
    return usb.core.find(idVendor=USB_VENDOR, idProduct=USB_PRODUCT) is not None
