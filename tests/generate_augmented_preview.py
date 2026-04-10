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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a small augmented preview dataset for visual inspection."
    )
    parser.add_argument("--count", type=int, default=12, help="How many valid words to render.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    parser.add_argument(
        "--output-dir",
        default=str(ROOT_DIR / "dataset" / "augmented-preview"),
        help="Where to write the preview dataset.",
    )
    parser.add_argument(
        "--fonts",
        nargs="+",
        default=["XM_ShuKai.ttf", "Sungar PaKa.ttf"],
        help="Font file names under manchufonts/ or explicit font paths.",
    )
    parser.add_argument(
        "--patch-shape",
        choices=["rectangle", "circle", "mixed"],
        default="circle",
        help="Shape used for stroke patch dropout in the preview set.",
    )
    parser.add_argument(
        "--augment-preset",
        choices=["light", "medium", "heavy"],
        default="medium",
        help="Predefined augmentation preset used for the preview set.",
    )
    parser.add_argument("--skip-invalid", action="store_true", default=True, help="Skip invalid rows.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    font_specs = MODULE.resolve_font_specs(args.fonts, root_dir=ROOT_DIR)

    preset = MODULE.get_augmentation_preset(args.augment_preset)

    stats = MODULE.generate_dataset(
        words_file=(ROOT_DIR / "AllWords.txt").resolve(),
        font_specs=font_specs,
        output_dir=output_dir,
        seed=args.seed,
        canvas_width=480,
        canvas_height=64,
        padding_percentage=0.05,
        skip_invalid=args.skip_invalid,
        max_samples=args.count,
        augmentation_config=MODULE.StrokeAugmentationConfig(
            enabled=True,
            threshold=preset.threshold,
            pixel_dropout_apply_prob=preset.pixel_dropout_apply_prob,
            pixel_dropout_ratio_min=preset.pixel_dropout_ratio_min,
            pixel_dropout_ratio_max=preset.pixel_dropout_ratio_max,
            patch_dropout_apply_prob=preset.patch_dropout_apply_prob,
            patch_count_min=preset.patch_count_min,
            patch_count_max=preset.patch_count_max,
            patch_size_min=preset.patch_size_min,
            patch_size_max=preset.patch_size_max,
            patch_shape=args.patch_shape,
        ),
    )

    print(f"Preview dataset written to: {output_dir}")
    print(stats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
