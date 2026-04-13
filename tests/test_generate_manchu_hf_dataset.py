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

    def test_stroke_augmentation_erases_some_foreground_pixels_deterministically(self) -> None:
        font_path = ROOT_DIR / "manchufonts" / "XM_ShuKai.ttf"
        font = ImageFont.truetype(str(font_path), MODULE.PROBE_FONT_SIZE)

        image = MODULE.render_sample_image(
            "ᠮᠠᠨᠵᡠ",
            font,
            canvas_width=480,
            canvas_height=64,
            padding_percentage=0.05,
        )
        baseline_mask = MODULE.get_stroke_mask(image, threshold=220)

        augmented = MODULE.apply_stroke_augmentations(
            image,
            config=MODULE.StrokeAugmentationConfig(
                enabled=True,
                threshold=220,
                pixel_dropout_apply_prob=1.0,
                pixel_dropout_ratio_min=0.05,
                pixel_dropout_ratio_max=0.05,
                patch_dropout_apply_prob=1.0,
                patch_count_min=2,
                patch_count_max=2,
                patch_size_min=3,
                patch_size_max=3,
                patch_shape="circle",
            ),
            rng=MODULE.random.Random(7),
        )
        augmented_mask = MODULE.get_stroke_mask(augmented, threshold=220)

        self.assertEqual(augmented.size, image.size)
        self.assertLess(augmented_mask.sum(), baseline_mask.sum())

    def test_circle_patch_dropout_keeps_changes_inside_patch_area(self) -> None:
        image = MODULE.Image.new("RGB", (32, 32), "white")
        for y in range(8, 24):
            for x in range(8, 24):
                image.putpixel((x, y), (0, 0, 0))

        augmented = MODULE.augment_stroke_patch_dropout(
            image,
            rng=MODULE.random.Random(3),
            patch_count=1,
            patch_size_min=8,
            patch_size_max=8,
            threshold=220,
            patch_shape="circle",
        )

        baseline_mask = MODULE.get_stroke_mask(image, threshold=220)
        augmented_mask = MODULE.get_stroke_mask(augmented, threshold=220)
        removed_mask = baseline_mask & ~augmented_mask

        self.assertGreater(removed_mask.sum(), 0)
        self.assertFalse(removed_mask[0:4, 0:4].any())

    def test_augmentation_preset_returns_expected_shape_defaults(self) -> None:
        light = MODULE.get_augmentation_preset("light")
        medium = MODULE.get_augmentation_preset("medium")
        heavy = MODULE.get_augmentation_preset("heavy")

        self.assertEqual(light.patch_shape, "circle")
        self.assertEqual(medium.patch_shape, "mixed")
        self.assertEqual(heavy.patch_shape, "mixed")
        self.assertLess(light.pixel_dropout_ratio_max, heavy.pixel_dropout_ratio_max)
        self.assertLess(light.tilt_apply_prob, heavy.tilt_apply_prob)
        self.assertLess(light.resize_percent_max, heavy.resize_percent_max)

    def test_random_tilt_preserves_canvas_size(self) -> None:
        image = MODULE.Image.new("RGB", (48, 48), "white")
        draw = MODULE.ImageDraw.Draw(image)
        draw.rectangle((20, 8, 28, 40), fill="black")
        baseline_box = MODULE.ImageOps.invert(image.convert("L")).getbbox()

        augmented = MODULE.augment_random_tilt(
            image,
            angle_degrees=3.0,
            rng=MODULE.random.Random(1),
        )
        augmented_box = MODULE.ImageOps.invert(augmented.convert("L")).getbbox()

        self.assertEqual(augmented.size, image.size)
        self.assertNotEqual(list(augmented.getdata()), list(image.getdata()))
        self.assertIsNotNone(baseline_box)
        self.assertIsNotNone(augmented_box)
        assert baseline_box is not None and augmented_box is not None
        self.assertGreaterEqual(augmented_box[0], baseline_box[0])
        self.assertGreaterEqual(augmented_box[1], baseline_box[1])
        self.assertLessEqual(augmented_box[2], baseline_box[2])
        self.assertLessEqual(augmented_box[3], baseline_box[3])

    def test_random_resize_preserves_canvas_size(self) -> None:
        image = MODULE.Image.new("RGB", (64, 32), "white")
        draw = MODULE.ImageDraw.Draw(image)
        draw.rectangle((20, 6, 40, 26), fill="black")
        baseline_box = MODULE.ImageOps.invert(image.convert("L")).getbbox()

        augmented = MODULE.augment_random_resize(
            image,
            resize_percent=0.03,
            rng=MODULE.random.Random(2),
        )
        augmented_box = MODULE.ImageOps.invert(augmented.convert("L")).getbbox()

        self.assertEqual(augmented.size, image.size)
        self.assertNotEqual(list(augmented.getdata()), list(image.getdata()))
        self.assertIsNotNone(baseline_box)
        self.assertIsNotNone(augmented_box)
        assert baseline_box is not None and augmented_box is not None
        self.assertLessEqual(augmented_box[2] - augmented_box[0], baseline_box[2] - baseline_box[0])
        self.assertLessEqual(augmented_box[3] - augmented_box[1], baseline_box[3] - baseline_box[1])

    def test_stroke_width_adjustment_preserves_canvas_size(self) -> None:
        image = MODULE.Image.new("RGB", (48, 48), "white")
        draw = MODULE.ImageDraw.Draw(image)
        draw.rectangle((21, 8, 27, 40), fill="black")

        augmented = MODULE.augment_stroke_width(
            image,
            rng=MODULE.random.Random(2),
            width_percent=0.03,
            threshold=220,
        )

        self.assertEqual(augmented.size, image.size)
        self.assertNotEqual(list(augmented.getdata()), list(image.getdata()))


if __name__ == "__main__":
    unittest.main()
