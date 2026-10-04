"""
SVG size helpers — physical units for ``Sketch.importSVG``.

Fusion's SVG import ignores the units on the root element and reads every
user unit as a CSS pixel (96 per inch): a drawing declared as
``width="100mm" viewBox="0 0 100 50"`` arrives 26.46 mm wide. This module
works out the factor that restores the declared size. Pure Python with no
``adsk`` import, so it can be unit-tested outside Fusion.
"""

import re
import xml.etree.ElementTree as ET

# Length of one unit in cm (CSS absolute units)
_CM_PER_UNIT = {
    "mm": 0.1,
    "cm": 1.0,
    "q": 0.025,
    "in": 2.54,
    "pt": 2.54 / 72,
    "pc": 2.54 / 6,
    "px": 2.54 / 96,
}
# What Fusion assumes for one SVG user unit
FUSION_CM_PER_USER_UNIT = 2.54 / 96

_LENGTH = re.compile(r"^\s*([0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)\s*([a-zA-Z%]*)\s*$")


def parse_length_cm(value: str | None) -> float | None:
    """'100mm' -> 10.0. None for missing, relative (%, em) or bad values."""
    if not value:
        return None
    match = _LENGTH.match(value)
    if not match:
        return None
    number, unit = float(match.group(1)), match.group(2).lower() or "px"
    factor = _CM_PER_UNIT.get(unit)
    return number * factor if factor is not None else None


def unit_scale(svg_text: str) -> float:
    """Factor to multiply Fusion's import scale by to get the declared size.

    Needs a root ``width`` with an absolute unit and a ``viewBox``; without
    a viewBox, user units are pixels and Fusion's reading is already
    right. Returns 1.0 whenever the size can't be determined.
    """
    try:
        root = ET.fromstring(svg_text)
    except ET.ParseError:
        return 1.0
    width_cm = parse_length_cm(root.get("width"))
    view_box = root.get("viewBox")
    if width_cm is None or not view_box:
        return 1.0
    try:
        vb_width = float(view_box.replace(",", " ").split()[2])
    except (IndexError, ValueError):
        return 1.0
    if vb_width <= 0:
        return 1.0
    return width_cm / (vb_width * FUSION_CM_PER_USER_UNIT)
