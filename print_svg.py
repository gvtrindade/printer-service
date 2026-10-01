#!/usr/bin/env python3
"""CLI wrapper — print a single SVG file on the RONGTA RP420 (hardware debugging)."""
import argparse
import sys
from pathlib import Path

from printer import render_label, send_to_printer, PrinterError


def main():
    parser = argparse.ArgumentParser(
        description="Print SVG file on a RONGTA RP420 thermal label printer (ZPL)")
    parser.add_argument("svg_file", help="Path to SVG file")
    parser.add_argument("--copies", type=int, default=1,
                        help="Number of labels to print (default: 1)")
    args = parser.parse_args()

    svg_file = Path(args.svg_file)
    if not svg_file.exists():
        print(f"Error: file '{args.svg_file}' not found", file=sys.stderr)
        sys.exit(1)

    svg_text = svg_file.read_text()
    zpl = render_label(svg_text)

    try:
        for i in range(args.copies):
            send_to_printer(zpl)
        print(f"Printed '{args.svg_file}' ({args.copies} cop{'ies' if args.copies > 1 else 'y'})")
    except PrinterError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
