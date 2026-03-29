from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

from PIL import ImageFont, ImageOps


ROOT_DIR = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT_DIR / "scripts" / "generate_manchu_hf_dataset.py"
SPEC = importlib.util.spec_from_file_location("generate_manchu_hf_dataset", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class RomanConversionTests(unittest.TestCase):
    def test_alias_normalization_matches_frontend_rule(self) -> None:
        conversion = MODULE.roman_to_manchu("SHuV")

        self.assertEqual(conversion.normalized, "šuū")
        self.assertEqual(conversion.manchu, "ᡧᡠᡡ")
        self.assertEqual(conversion.errors, ())

    def test_longest_ng_match_is_preserved(self) -> None:
        conversion = MODULE.roman_to_manchu("angga")

        self.assertEqual(conversion.manchu, "ᠠᠩᡤᠠ")
        self.assertEqual(conversion.errors, ())

    def test_unknown_fragments_are_reported(self) -> None:
        conversion = MODULE.roman_to_manchu("qa")

        self.assertEqual(conversion.manchu, "qᠠ")
        self.assertEqual([(error.start, error.end, error.raw) for error in conversion.errors], [(0, 1, "q")])


class PartitioningTests(unittest.TestCase):
    def test_partition_sizes_differ_by_at_most_one(self) -> None:
        rows = [
            MODULE.ConvertedRow(
                source_line_number=index + 1,
                roman_raw=f"word-{index}",
                roman_normalized=f"word-{index}",
                manchu="ᠠ",
            )
            for index in range(11)
        ]
        fonts = [
            MODULE.FontSpec(id=f"font-{index}", file_name=f"font-{index}.ttf", path=Path(f"/tmp/font-{index}.ttf"))
            for index in range(3)
        ]

        buckets = MODULE.partition_rows(rows, fonts, seed=42)
        bucket_sizes = [len(bucket_rows) for _, bucket_rows in buckets]

        self.assertEqual(sum(bucket_sizes), len(rows))
        self.assertLessEqual(max(bucket_sizes) - min(bucket_sizes), 1)


class RenderingTests(unittest.TestCase):
    def test_rendered_image_has_fixed_canvas_left_padding_and_vertical_padding(self) -> None:
        font_path = ROOT_DIR / "manchufonts" / "XM_ShuKai.ttf"
        font = ImageFont.truetype(str(font_path), MODULE.PROBE_FONT_SIZE)

        image = MODULE.render_sample_image(
            "ᠮᠠᠨᠵᡠ",
            font,
            canvas_width=480,
            canvas_height=64,
            padding_percentage=0.05,
        )
        non_white_box = ImageOps.invert(image.convert("L")).getbbox()

        self.assertEqual(image.width, 480)
        self.assertEqual(image.height, 64)
        self.assertIsNotNone(non_white_box)
        assert non_white_box is not None
        self.assertGreaterEqual(non_white_box[0], 4)
        self.assertGreater(non_white_box[2], 0)
        self.assertLess(non_white_box[2], 480)
        top_padding = non_white_box[1]
        bottom_padding = image.height - non_white_box[3]
        self.assertGreaterEqual(top_padding, 4)
        self.assertGreaterEqual(bottom_padding, 4)
        self.assertLessEqual(abs(top_padding - bottom_padding), 1)


if __name__ == "__main__":
    unittest.main()
