"""Tests for the add-in's SVG unit helpers (pure Python, no Fusion)."""

import importlib.util
import math
import os

_PATH = os.path.join(os.path.dirname(__file__), "..", "addon", "server",
                     "svg_units.py")
# Load the file directly: importing the add-in package would pull in adsk.
_spec = importlib.util.spec_from_file_location("svg_units", _PATH)
svg_units = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(svg_units)


def _svg(attrs: str) -> str:
    return f'<svg xmlns="http://www.w3.org/2000/svg" {attrs}><rect/></svg>'


class TestParseLength:
    def test_units(self):
        assert math.isclose(svg_units.parse_length_cm("100mm"), 10.0)
        assert math.isclose(svg_units.parse_length_cm("2.5cm"), 2.5)
        assert math.isclose(svg_units.parse_length_cm("1in"), 2.54)
        assert math.isclose(svg_units.parse_length_cm("72pt"), 2.54)
        assert math.isclose(svg_units.parse_length_cm("96"), 2.54)
        assert math.isclose(svg_units.parse_length_cm(" 1e2 MM "), 10.0)

    def test_unusable(self):
        for value in (None, "", "100%", "10em", "wide"):
            assert svg_units.parse_length_cm(value) is None


class TestUnitScale:
    def test_mm_with_viewbox(self):
        # Measured in Fusion 2705: this file arrived 2.646 cm wide at scale 1
        s = svg_units.unit_scale(
            _svg('width="100mm" height="50mm" viewBox="0 0 100 50"'))
        assert math.isclose(2.6458 * s, 10.0, rel_tol=1e-3)

    def test_viewbox_with_commas(self):
        s = svg_units.unit_scale(_svg('width="10cm" viewBox="0,0,1000,500"'))
        assert math.isclose(1000 * svg_units.FUSION_CM_PER_USER_UNIT * s, 10)

    def test_pixels_are_left_alone(self):
        assert svg_units.unit_scale(
            _svg('width="400" viewBox="0 0 400 200"')) == 1.0
        assert svg_units.unit_scale(
            _svg('width="400px" viewBox="0 0 400 200"')) == 1.0

    def test_falls_back_to_one(self):
        assert svg_units.unit_scale(_svg('width="100mm"')) == 1.0
        assert svg_units.unit_scale(_svg('viewBox="0 0 10 10"')) == 1.0
        assert svg_units.unit_scale(_svg('width="50%" viewBox="0 0 1 1"')) \
            == 1.0
        assert svg_units.unit_scale(_svg('width="1mm" viewBox="0 0 0 1"')) \
            == 1.0
        assert svg_units.unit_scale("not xml") == 1.0
