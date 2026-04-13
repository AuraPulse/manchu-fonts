#!/usr/bin/env python3

from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT_DIR / "scripts" / "generate_manchu_hf_dataset.py"
SPEC = importlib.util.spec_from_file_location("generate_manchu_hf_dataset", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


DEFAULT_FONTS = [
    "XM_LiuYe.ttf",
    "XM_ShuKai.ttf",
    "XM_WenQin.ttf",
    "XM_XingShu.ttf",
    "XM_YingBi.ttf",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate the full augmented Manchu dataset for all valid words."
    )
    parser.add_argument(
        "--words-file",
        default=str(ROOT_DIR / "AllWords.txt"),
        help="Path to the source word list.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(ROOT_DIR / "dataset" / "hf-all-augmented"),
        help="Where to write the generated dataset.",
    )
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    parser.add_argument(
        "--fonts",
        nargs="+",
        default=DEFAULT_FONTS,
        help="Font file names under manchufonts/ or explicit font paths.",
    )
    parser.add_argument("--canvas-width", type=int, default=480, help="Output image width.")
    parser.add_argument("--canvas-height", type=int, default=64, help="Output image height.")
    parser.add_argument(
        "--padding-percentage",
        type=float,
        default=0.05,
        help="Padding percentage used during rendering.",
    )
    parser.add_argument("--skip-invalid", action="store_true", default=True, help="Skip invalid rows.")
    parser.add_argument(
        "--disable-augmentation",
        action="store_true",
        help="Generate the full dataset without any augmentation.",
    )
    parser.add_argument("--tilt-apply-prob", type=float, default=0.9, help="Rotation apply probability.")
    parser.add_argument("--tilt-degrees-min", type=float, default=1.0, help="Minimum rotation in degrees.")
    parser.add_argument("--tilt-degrees-max", type=float, default=5.0, help="Maximum rotation in degrees.")
    parser.add_argument(
        "--stroke-width-apply-prob",
        type=float,
        default=0.9,
        help="Thinner/thicker apply probability.",
    )
    parser.add_argument(
        "--stroke-width-percent-min",
        type=float,
        default=0.01,
        help="Minimum thinner/thicker magnitude.",
    )
    parser.add_argument(
        "--stroke-width-percent-max",
        type=float,
        default=0.05,
        help="Maximum thinner/thicker magnitude.",
    )
    parser.add_argument("--resize-apply-prob", type=float, default=0.9, help="Resize apply probability.")
    parser.add_argument(
        "--resize-percent-min",
        type=float,
        default=0.01,
        help="Minimum shrink magnitude.",
    )
    parser.add_argument(
        "--resize-percent-max",
        type=float,
        default=0.05,
        help="Maximum shrink magnitude.",
    )
    parser.add_argument(
        "--pixel-dropout-apply-prob",
        type=float,
        default=0.9,
        help="Stroke pixel dropout apply probability.",
    )
    parser.add_argument(
        "--pixel-dropout-ratio-min",
        type=float,
        default=0.03,
        help="Minimum stroke pixel dropout ratio.",
    )
    parser.add_argument(
        "--pixel-dropout-ratio-max",
        type=float,
        default=0.10,
        help="Maximum stroke pixel dropout ratio.",
    )
    parser.add_argument(
        "--patch-dropout-apply-prob",
        type=float,
        default=0.9,
        help="Stroke patch dropout apply probability.",
    )
    parser.add_argument("--patch-count-min", type=int, default=4, help="Minimum patch dropout count.")
    parser.add_argument("--patch-count-max", type=int, default=8, help="Maximum patch dropout count.")
    parser.add_argument("--patch-size-min", type=int, default=4, help="Minimum patch size.")
    parser.add_argument("--patch-size-max", type=int, default=10, help="Maximum patch size.")
    parser.add_argument(
        "--patch-shape",
        choices=["rectangle", "circle", "mixed"],
        default="rectangle",
        help="Patch shape used for dropout.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    font_specs = MODULE.resolve_font_specs(args.fonts, root_dir=ROOT_DIR)

    augmentation_config = MODULE.StrokeAugmentationConfig(
        enabled=not args.disable_augmentation,
        threshold=220,
        tilt_apply_prob=args.tilt_apply_prob,
        tilt_degrees_min=args.tilt_degrees_min,
        tilt_degrees_max=args.tilt_degrees_max,
        stroke_width_apply_prob=args.stroke_width_apply_prob,
        stroke_width_percent_min=args.stroke_width_percent_min,
        stroke_width_percent_max=args.stroke_width_percent_max,
        resize_apply_prob=args.resize_apply_prob,
        resize_percent_min=args.resize_percent_min,
        resize_percent_max=args.resize_percent_max,
        pixel_dropout_apply_prob=args.pixel_dropout_apply_prob,
        pixel_dropout_ratio_min=args.pixel_dropout_ratio_min,
        pixel_dropout_ratio_max=args.pixel_dropout_ratio_max,
        patch_dropout_apply_prob=args.patch_dropout_apply_prob,
        patch_count_min=args.patch_count_min,
        patch_count_max=args.patch_count_max,
        patch_size_min=args.patch_size_min,
        patch_size_max=args.patch_size_max,
        patch_shape=args.patch_shape,
    )

    stats = MODULE.generate_dataset(
        words_file=Path(args.words_file).resolve(),
        font_specs=font_specs,
        output_dir=output_dir,
        seed=args.seed,
        canvas_width=args.canvas_width,
        canvas_height=args.canvas_height,
        padding_percentage=args.padding_percentage,
        skip_invalid=args.skip_invalid,
        max_samples=None,
        augmentation_config=augmentation_config,
    )

    print(f"Full dataset written to: {output_dir}")
    print(stats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
