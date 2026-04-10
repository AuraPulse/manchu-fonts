#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
import math
import numpy as np
import random
import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
import unicodedata

from PIL import Image, ImageDraw, ImageFont, ImageOps


ALIAS_RULES: list[tuple[str, str]] = [
    ("s\u030c", "š"),
    ("u\u0304", "ū"),
    ("sh", "š"),
    ("uu", "ū"),
    ("x", "š"),
    ("v", "ū"),
    ("ü", "ū"),
]

TOKEN_MAP = {
    "ng": "ᠩ",
    "a": "ᠠ",
    "e": "ᡝ",
    "i": "ᡳ",
    "o": "ᠣ",
    "u": "ᡠ",
    "ū": "ᡡ",
    "n": "ᠨ",
    "b": "ᠪ",
    "p": "ᡦ",
    "k": "ᡴ",
    "g": "ᡤ",
    "h": "ᡥ",
    "m": "ᠮ",
    "l": "ᠯ",
    "s": "ᠰ",
    "š": "ᡧ",
    "t": "ᡨ",
    "d": "ᡩ",
    "c": "ᠴ",
    "j": "ᠵ",
    "y": "ᠶ",
    "r": "ᡵ",
    "f": "ᡶ",
    "w": "ᠸ",
}

TOKENS = sorted(TOKEN_MAP.keys(), key=len, reverse=True)
PROBE_FONT_SIZE = 256
RESAMPLE_LANCZOS = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS


@dataclass(frozen=True)
class NormalizedUnit:
    value: str
    source_start: int
    source_end: int


@dataclass(frozen=True)
class RomanError:
    start: int
    end: int
    raw: str


@dataclass(frozen=True)
class RomanConversion:
    normalized: str
    manchu: str
    errors: tuple[RomanError, ...]


@dataclass(frozen=True)
class SourceRow:
    source_line_number: int
    roman_raw: str


@dataclass(frozen=True)
class ConvertedRow:
    source_line_number: int
    roman_raw: str
    roman_normalized: str
    manchu: str


@dataclass(frozen=True)
class InvalidRow:
    source_line_number: int
    roman_raw: str
    roman_normalized: str
    error_fragments: str


@dataclass(frozen=True)
class FontSpec:
    id: str
    file_name: str
    path: Path


@dataclass(frozen=True)
class DatasetSample:
    sample_id: str
    split: str
    partition_index: int
    font: FontSpec
    row: ConvertedRow


@dataclass(frozen=True)
class StrokeAugmentationConfig:
    enabled: bool = False
    threshold: int = 220
    pixel_dropout_apply_prob: float = 0.0
    pixel_dropout_ratio_min: float = 0.01
    pixel_dropout_ratio_max: float = 0.03
    patch_dropout_apply_prob: float = 0.0
    patch_count_min: int = 1
    patch_count_max: int = 3
    patch_size_min: int = 2
    patch_size_max: int = 6
    patch_shape: str = "rectangle"


def get_augmentation_preset(name: str) -> StrokeAugmentationConfig:
    presets = {
        "light": StrokeAugmentationConfig(
            enabled=True,
            threshold=220,
            pixel_dropout_apply_prob=0.45,
            pixel_dropout_ratio_min=0.006,
            pixel_dropout_ratio_max=0.018,
            patch_dropout_apply_prob=0.35,
            patch_count_min=1,
            patch_count_max=2,
            patch_size_min=2,
            patch_size_max=4,
            patch_shape="circle",
        ),
        "medium": StrokeAugmentationConfig(
            enabled=True,
            threshold=220,
            pixel_dropout_apply_prob=0.65,
            pixel_dropout_ratio_min=0.01,
            pixel_dropout_ratio_max=0.03,
            patch_dropout_apply_prob=0.65,
            patch_count_min=1,
            patch_count_max=3,
            patch_size_min=2,
            patch_size_max=6,
            patch_shape="mixed",
        ),
        "heavy": StrokeAugmentationConfig(
            enabled=True,
            threshold=220,
            pixel_dropout_apply_prob=0.9,
            pixel_dropout_ratio_min=0.02,
            pixel_dropout_ratio_max=0.06,
            patch_dropout_apply_prob=0.9,
            patch_count_min=3,
            patch_count_max=6,
            patch_size_min=3,
            patch_size_max=9,
            patch_shape="mixed",
        ),
    }
    if name not in presets:
        raise ValueError(f"Unknown augmentation preset: {name}")
    return presets[name]


def slugify(value: str) -> str:
    lowered = re.sub(r"\.[^.]+$", "", value.strip().lower())
    return re.sub(r"^-+|-+$", "", re.sub(r"[^a-z0-9]+", "-", lowered))


def is_passthrough(value: str) -> bool:
    category = unicodedata.category(value)
    return value.isspace() or category[0] in {"P", "S", "N"}


def matches_known_token(normalized: str, index: int) -> bool:
    return any(normalized.startswith(token, index) for token in TOKENS)


def normalize_roman_with_map(input_text: str) -> tuple[str, list[NormalizedUnit]]:
    lower_cased = input_text.lower()
    units: list[NormalizedUnit] = []
    index = 0

    while index < len(lower_cased):
        remaining = lower_cased[index:]
        alias = next((rule for rule in ALIAS_RULES if remaining.startswith(rule[0])), None)

        if alias is not None:
            raw, value = alias
            units.append(
                NormalizedUnit(
                    value=value,
                    source_start=index,
                    source_end=index + len(raw),
                )
            )
            index += len(raw)
            continue

        current_character = lower_cased[index]
        units.append(
            NormalizedUnit(
                value=current_character,
                source_start=index,
                source_end=index + len(current_character),
            )
        )
        index += len(current_character)

    return "".join(unit.value for unit in units), units


def roman_to_manchu(input_text: str) -> RomanConversion:
    normalized, units = normalize_roman_with_map(input_text)
    manchu_parts: list[str] = []
    errors: list[RomanError] = []
    index = 0

    while index < len(normalized):
        current_value = normalized[index]

        if is_passthrough(current_value):
            end = index + 1
            while end < len(normalized) and is_passthrough(normalized[end]):
                end += 1

            manchu_parts.append(input_text[units[index].source_start : units[end - 1].source_end])
            index = end
            continue

        matched_token = next((token for token in TOKENS if normalized.startswith(token, index)), None)
        if matched_token is not None:
            manchu_parts.append(TOKEN_MAP[matched_token])
            index += len(matched_token)
            continue

        end = index + 1
        while (
            end < len(normalized)
            and not is_passthrough(normalized[end])
            and not matches_known_token(normalized, end)
        ):
            end += 1

        raw_fragment = input_text[units[index].source_start : units[end - 1].source_end]
        errors.append(
            RomanError(
                start=units[index].source_start,
                end=units[end - 1].source_end,
                raw=raw_fragment,
            )
        )
        manchu_parts.append(raw_fragment)
        index = end

    return RomanConversion(
        normalized=normalized,
        manchu="".join(manchu_parts),
        errors=tuple(errors),
    )


def read_source_rows(words_file: Path) -> list[SourceRow]:
    rows: list[SourceRow] = []

    with words_file.open("r", encoding="utf-8") as handle:
        for source_line_number, line in enumerate(handle, start=1):
            roman_raw = line.strip()
            if roman_raw:
                rows.append(SourceRow(source_line_number=source_line_number, roman_raw=roman_raw))

    return rows


def convert_rows(rows: Iterable[SourceRow], skip_invalid: bool) -> tuple[list[ConvertedRow], list[InvalidRow]]:
    converted_rows: list[ConvertedRow] = []
    invalid_rows: list[InvalidRow] = []

    for row in rows:
        conversion = roman_to_manchu(row.roman_raw)
        if conversion.errors:
            invalid_row = InvalidRow(
                source_line_number=row.source_line_number,
                roman_raw=row.roman_raw,
                roman_normalized=conversion.normalized,
                error_fragments=" | ".join(error.raw for error in conversion.errors),
            )
            if not skip_invalid:
                raise ValueError(
                    f"Invalid Roman input on line {row.source_line_number}: "
                    f"{row.roman_raw!r} -> {invalid_row.error_fragments}"
                )
            invalid_rows.append(invalid_row)
            continue

        converted_rows.append(
            ConvertedRow(
                source_line_number=row.source_line_number,
                roman_raw=row.roman_raw,
                roman_normalized=conversion.normalized,
                manchu=conversion.manchu,
            )
        )

    return converted_rows, invalid_rows


def resolve_font_specs(font_args: list[str], root_dir: Path) -> list[FontSpec]:
    font_dir = root_dir / "manchufonts"
    specs: list[FontSpec] = []

    for font_arg in font_args:
        explicit_path = Path(font_arg)
        if explicit_path.exists():
            resolved_path = explicit_path.resolve()
        else:
            candidate_path = (font_dir / font_arg).resolve()
            if not candidate_path.exists():
                raise FileNotFoundError(
                    f"Could not find font {font_arg!r}. "
                    f"Pass a valid path or a file name that exists under {font_dir}."
                )
            resolved_path = candidate_path

        if resolved_path.suffix.lower() not in {".ttf", ".otf"}:
            raise ValueError(f"Unsupported font format: {resolved_path.name}")

        specs.append(
            FontSpec(
                id=slugify(resolved_path.name),
                file_name=resolved_path.name,
                path=resolved_path,
            )
        )

    return specs


def partition_rows(rows: list[ConvertedRow], font_specs: list[FontSpec], seed: int) -> list[tuple[FontSpec, list[ConvertedRow]]]:
    shuffled_rows = list(rows)
    random.Random(seed).shuffle(shuffled_rows)

    bucket_count = len(font_specs)
    base_size = len(shuffled_rows) // bucket_count
    remainder = len(shuffled_rows) % bucket_count

    buckets: list[tuple[FontSpec, list[ConvertedRow]]] = []
    cursor = 0

    for index, font_spec in enumerate(font_specs):
        bucket_size = base_size + (1 if index < remainder else 0)
        bucket_rows = shuffled_rows[cursor : cursor + bucket_size]
        buckets.append((font_spec, bucket_rows))
        cursor += bucket_size

    return buckets


def split_bucket(rows: list[ConvertedRow], train_ratio: float = 0.9) -> tuple[list[ConvertedRow], list[ConvertedRow]]:
    if not rows:
        return [], []
    if len(rows) == 1:
        return rows[:], []

    train_count = int(len(rows) * train_ratio)
    train_count = max(1, min(train_count, len(rows) - 1))
    return rows[:train_count], rows[train_count:]


def get_stroke_mask(image: Image.Image, threshold: int) -> np.ndarray:
    grayscale = np.asarray(image.convert("L"))
    return grayscale < threshold


def augment_stroke_pixel_dropout(
    image: Image.Image,
    rng: random.Random,
    drop_ratio: float,
    threshold: int,
) -> Image.Image:
    if drop_ratio <= 0:
        return image

    grayscale = np.asarray(image.convert("L")).copy()
    stroke_mask = get_stroke_mask(image, threshold)
    stroke_coords = np.argwhere(stroke_mask)

    if len(stroke_coords) == 0:
        return image

    drop_count = min(len(stroke_coords), max(1, int(len(stroke_coords) * drop_ratio)))
    np_rng = np.random.default_rng(rng.randrange(1 << 63))
    drop_indices = np_rng.choice(len(stroke_coords), size=drop_count, replace=False)
    drop_coords = stroke_coords[drop_indices]
    grayscale[drop_coords[:, 0], drop_coords[:, 1]] = 255
    return Image.fromarray(grayscale, mode="L").convert("RGB")


def augment_stroke_patch_dropout(
    image: Image.Image,
    rng: random.Random,
    patch_count: int,
    patch_size_min: int,
    patch_size_max: int,
    threshold: int,
    patch_shape: str,
) -> Image.Image:
    if patch_count <= 0:
        return image

    grayscale = np.asarray(image.convert("L")).copy()
    stroke_mask = get_stroke_mask(image, threshold)
    stroke_coords = np.argwhere(stroke_mask)

    if len(stroke_coords) == 0:
        return image

    np_rng = np.random.default_rng(rng.randrange(1 << 63))

    for _ in range(patch_count):
        center_y, center_x = stroke_coords[np_rng.integers(0, len(stroke_coords))]
        current_shape = patch_shape if patch_shape != "mixed" else rng.choice(["rectangle", "circle"])
        patch_height = rng.randint(patch_size_min, patch_size_max)
        patch_width = rng.randint(patch_size_min, patch_size_max)
        y0 = max(0, center_y - patch_height // 2)
        x0 = max(0, center_x - patch_width // 2)
        y1 = min(grayscale.shape[0], y0 + patch_height)
        x1 = min(grayscale.shape[1], x0 + patch_width)

        local_stroke_mask = stroke_mask[y0:y1, x0:x1]
        if current_shape == "rectangle":
            grayscale[y0:y1, x0:x1][local_stroke_mask] = 255
            continue

        local_height = y1 - y0
        local_width = x1 - x0
        yy, xx = np.ogrid[:local_height, :local_width]
        center_yy = (local_height - 1) / 2.0
        center_xx = (local_width - 1) / 2.0
        radius_y = max(local_height / 2.0, 1.0)
        radius_x = max(local_width / 2.0, 1.0)
        ellipse_mask = (((yy - center_yy) / radius_y) ** 2 + ((xx - center_xx) / radius_x) ** 2) <= 1.0
        grayscale[y0:y1, x0:x1][local_stroke_mask & ellipse_mask] = 255

    return Image.fromarray(grayscale, mode="L").convert("RGB")


def apply_stroke_augmentations(
    image: Image.Image,
    config: StrokeAugmentationConfig,
    rng: random.Random,
) -> Image.Image:
    if not config.enabled:
        return image

    if not 0 <= config.pixel_dropout_apply_prob <= 1:
        raise ValueError("pixel_dropout_apply_prob must be in [0, 1].")
    if not 0 <= config.patch_dropout_apply_prob <= 1:
        raise ValueError("patch_dropout_apply_prob must be in [0, 1].")
    if config.pixel_dropout_ratio_min > config.pixel_dropout_ratio_max:
        raise ValueError("pixel_dropout_ratio_min must be <= pixel_dropout_ratio_max.")
    if config.patch_count_min > config.patch_count_max:
        raise ValueError("patch_count_min must be <= patch_count_max.")
    if config.patch_size_min > config.patch_size_max:
        raise ValueError("patch_size_min must be <= patch_size_max.")
    if config.patch_shape not in {"rectangle", "circle", "mixed"}:
        raise ValueError("patch_shape must be one of: rectangle, circle, mixed.")

    augmented = image

    if rng.random() < config.pixel_dropout_apply_prob:
        drop_ratio = rng.uniform(config.pixel_dropout_ratio_min, config.pixel_dropout_ratio_max)
        augmented = augment_stroke_pixel_dropout(
            augmented,
            rng=rng,
            drop_ratio=drop_ratio,
            threshold=config.threshold,
        )

    if rng.random() < config.patch_dropout_apply_prob:
        patch_count = rng.randint(config.patch_count_min, config.patch_count_max)
        augmented = augment_stroke_patch_dropout(
            augmented,
            rng=rng,
            patch_count=patch_count,
            patch_size_min=config.patch_size_min,
            patch_size_max=config.patch_size_max,
            threshold=config.threshold,
            patch_shape=config.patch_shape,
        )

    return augmented


def render_tight_content(text: str, font: ImageFont.FreeTypeFont) -> Image.Image:
    bbox = font.getbbox(text)
    if bbox is None:
        raise ValueError(f"Could not measure text bbox for {text!r}.")

    bbox_width = bbox[2] - bbox[0]
    bbox_height = bbox[3] - bbox[1]
    if bbox_width <= 0 or bbox_height <= 0:
        raise ValueError(f"Measured an empty bbox for {text!r}.")

    margin = max(16, PROBE_FONT_SIZE // 8)
    temp_width = bbox_width + margin * 2
    temp_height = bbox_height + margin * 2

    temp_image = Image.new("L", (temp_width, temp_height), 255)
    draw = ImageDraw.Draw(temp_image)
    draw.text((margin - bbox[0], margin - bbox[1]), text, font=font, fill=0)

    content_box = ImageOps.invert(temp_image).getbbox()
    if content_box is None:
        raise ValueError(f"Rendered an empty image for {text!r}.")

    return temp_image.crop(content_box)


def render_sample_image(
    text: str,
    font: ImageFont.FreeTypeFont,
    canvas_width: int,
    canvas_height: int,
    padding_percentage: float,
) -> Image.Image:
    if canvas_width <= 0:
        raise ValueError("canvas_width must be positive.")
    if canvas_height <= 0:
        raise ValueError("canvas_height must be positive.")
    if not 0 <= padding_percentage < 0.5:
        raise ValueError("padding_percentage must be in [0, 0.5).")

    content = render_tight_content(text, font)
    left_padding = math.ceil(canvas_width * padding_percentage)
    top_padding = math.ceil(canvas_height * padding_percentage)
    bottom_padding = math.ceil(canvas_height * padding_percentage)
    inner_width = max(1, canvas_width - left_padding)
    inner_height = max(1, canvas_height - top_padding - bottom_padding)
    scale = min(inner_width / content.width, inner_height / content.height)
    scaled_width = max(1, min(inner_width, math.floor(content.width * scale)))
    scaled_height = max(1, min(inner_height, math.floor(content.height * scale)))

    resized_inner = content.resize((scaled_width, scaled_height), RESAMPLE_LANCZOS).convert("RGB")
    canvas = Image.new("RGB", (canvas_width, canvas_height), "white")

    x_offset = left_padding
    y_offset = top_padding + max(0, (inner_height - scaled_height) // 2)
    canvas.paste(resized_inner, (x_offset, y_offset))

    return canvas


def build_samples(buckets: list[tuple[FontSpec, list[ConvertedRow]]]) -> list[DatasetSample]:
    total_rows = sum(len(rows) for _, rows in buckets)
    sample_id_width = max(6, len(str(total_rows)))
    samples: list[DatasetSample] = []
    sample_number = 1

    for partition_index, (font_spec, rows) in enumerate(buckets):
        train_rows, validation_rows = split_bucket(rows)

        for split_name, split_rows in (("train", train_rows), ("validation", validation_rows)):
            for row in split_rows:
                samples.append(
                    DatasetSample(
                        sample_id=str(sample_number).zfill(sample_id_width),
                        split=split_name,
                        partition_index=partition_index,
                        font=font_spec,
                        row=row,
                    )
                )
                sample_number += 1

    return samples


def write_invalid_rows(output_dir: Path, invalid_rows: list[InvalidRow]) -> None:
    invalid_rows_path = output_dir / "invalid_rows.csv"
    with invalid_rows_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["source_line_number", "roman", "roman_normalized", "error_fragments"])
        for row in invalid_rows:
            writer.writerow(
                [
                    row.source_line_number,
                    row.roman_raw,
                    row.roman_normalized,
                    row.error_fragments,
                ]
            )


def write_summary(
    output_dir: Path,
    words_file: Path,
    font_specs: list[FontSpec],
    samples: list[DatasetSample],
    invalid_rows: list[InvalidRow],
    seed: int,
    canvas_width: int,
    canvas_height: int,
    padding_percentage: float,
    max_samples: int | None,
    augmentation_config: StrokeAugmentationConfig,
) -> None:
    split_counts = defaultdict(int)
    per_font_counts: dict[str, dict[str, int | str]] = {
        font.id: {
            "total": 0,
            "train": 0,
            "validation": 0,
        }
        for font in font_specs
    }

    for sample in samples:
        split_counts[sample.split] += 1
        per_font_counts[sample.font.id]["total"] += 1
        per_font_counts[sample.font.id][sample.split] += 1

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "words_file": str(words_file.resolve()),
        "seed": seed,
        "canvas_width": canvas_width,
        "canvas_height": canvas_height,
        "padding_percentage": padding_percentage,
        "max_samples": max_samples,
        "total_samples": len(samples),
        "invalid_samples": len(invalid_rows),
        "stroke_augmentation": {
            "enabled": augmentation_config.enabled,
            "threshold": augmentation_config.threshold,
            "pixel_dropout_apply_prob": augmentation_config.pixel_dropout_apply_prob,
            "pixel_dropout_ratio_min": augmentation_config.pixel_dropout_ratio_min,
            "pixel_dropout_ratio_max": augmentation_config.pixel_dropout_ratio_max,
            "patch_dropout_apply_prob": augmentation_config.patch_dropout_apply_prob,
            "patch_count_min": augmentation_config.patch_count_min,
            "patch_count_max": augmentation_config.patch_count_max,
            "patch_size_min": augmentation_config.patch_size_min,
            "patch_size_max": augmentation_config.patch_size_max,
            "patch_shape": augmentation_config.patch_shape,
        },
        "splits": {
            "train": split_counts["train"],
            "validation": split_counts["validation"],
        },
        "fonts": [
            {
                "id": font.id,
                "file_name": font.file_name,
                "path": str(font.path),
                "counts": per_font_counts[font.id],
            }
            for font in font_specs
        ],
    }

    summary_path = output_dir / "summary.json"
    with summary_path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2)


def generate_dataset(
    words_file: Path,
    font_specs: list[FontSpec],
    output_dir: Path,
    seed: int,
    canvas_width: int,
    canvas_height: int,
    padding_percentage: float,
    skip_invalid: bool,
    max_samples: int | None = None,
    augmentation_config: StrokeAugmentationConfig = StrokeAugmentationConfig(),
) -> dict[str, int]:
    source_rows = read_source_rows(words_file)
    converted_rows, invalid_rows = convert_rows(source_rows, skip_invalid=skip_invalid)
    if max_samples is not None:
        if max_samples <= 0:
            raise ValueError("max_samples must be positive when provided.")
        limited_rows = list(converted_rows)
        random.Random(seed).shuffle(limited_rows)
        converted_rows = limited_rows[:max_samples]
    buckets = partition_rows(converted_rows, font_specs, seed=seed)
    samples = build_samples(buckets)

    output_dir.mkdir(parents=True, exist_ok=True)
    if invalid_rows:
        write_invalid_rows(output_dir, invalid_rows)

    font_cache = {
        font.id: ImageFont.truetype(str(font.path), PROBE_FONT_SIZE)
        for font in font_specs
    }

    split_dirs = {
        "train": output_dir / "train",
        "validation": output_dir / "validation",
    }

    metadata_handles: dict[str, object] = {}
    metadata_writers: dict[str, dict[str, csv.writer]] = {}
    augmentation_rng = random.Random(seed ^ 0x5F3759DF)

    try:
        for split_name, split_dir in split_dirs.items():
            split_dir.mkdir(parents=True, exist_ok=True)
            metadata_path = split_dir / "metadata.csv"
            hf_metadata_path = split_dir / "metadata_hf.csv"

            metadata_handle = metadata_path.open("w", encoding="utf-8", newline="")
            hf_metadata_handle = hf_metadata_path.open("w", encoding="utf-8", newline="")

            metadata_handles[f"{split_name}:metadata"] = metadata_handle
            metadata_handles[f"{split_name}:hf_metadata"] = hf_metadata_handle

            metadata_writer = csv.writer(metadata_handle)
            metadata_writer.writerow(["im", "roman", "manchu"])

            hf_metadata_writer = csv.writer(hf_metadata_handle)
            hf_metadata_writer.writerow(["file_name", "roman", "manchu"])

            metadata_writers[split_name] = {
                "metadata": metadata_writer,
                "hf_metadata": hf_metadata_writer,
            }

        for index, sample in enumerate(samples, start=1):
            split_dir = split_dirs[sample.split]
            image_dir = split_dir / "images" / sample.font.id
            image_dir.mkdir(parents=True, exist_ok=True)
            image_path = image_dir / f"{sample.sample_id}.png"

            image = render_sample_image(
                text=sample.row.manchu,
                font=font_cache[sample.font.id],
                canvas_width=canvas_width,
                canvas_height=canvas_height,
                padding_percentage=padding_percentage,
            )
            image = apply_stroke_augmentations(
                image,
                config=augmentation_config,
                rng=random.Random(augmentation_rng.randrange(1 << 63)),
            )
            image.save(image_path, format="PNG")

            image_relpath = image_path.relative_to(split_dir).as_posix()

            metadata_writers[sample.split]["metadata"].writerow(
                [
                    image_relpath,
                    sample.row.roman_raw,
                    sample.row.manchu,
                ]
            )
            metadata_writers[sample.split]["hf_metadata"].writerow(
                [
                    image_relpath,
                    sample.row.roman_raw,
                    sample.row.manchu,
                ]
            )

            if index % 1000 == 0 or index == len(samples):
                print(f"Generated {index}/{len(samples)} images...")
    finally:
        for handle in metadata_handles.values():
            handle.close()

    write_summary(
        output_dir=output_dir,
        words_file=words_file,
        font_specs=font_specs,
        samples=samples,
        invalid_rows=invalid_rows,
        seed=seed,
        canvas_width=canvas_width,
        canvas_height=canvas_height,
        padding_percentage=padding_percentage,
        max_samples=max_samples,
        augmentation_config=augmentation_config,
    )

    return {
        "total_rows": len(source_rows),
        "valid_rows": len(converted_rows),
        "invalid_rows": len(invalid_rows),
        "train_rows": sum(1 for sample in samples if sample.split == "train"),
        "validation_rows": sum(1 for sample in samples if sample.split == "validation"),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a Hugging Face style Manchu image dataset from AllWords.txt."
    )
    parser.add_argument("--words-file", required=True, help="Path to the source word list.")
    parser.add_argument(
        "--fonts",
        required=True,
        nargs="+",
        help="Font file names under manchufonts/ or explicit font paths.",
    )
    parser.add_argument("--output-dir", required=True, help="Directory where the dataset will be written.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for deterministic partitioning.")
    parser.add_argument(
        "--canvas-width",
        type=int,
        default=480,
        help="Fixed output image width in pixels.",
    )
    parser.add_argument(
        "--canvas-height",
        type=int,
        default=64,
        help="Fixed output image height in pixels.",
    )
    parser.add_argument(
        "--padding-percentage",
        type=float,
        default=0.05,
        help="Padding applied on each side as a percentage of the canvas height.",
    )
    parser.add_argument(
        "--skip-invalid",
        action="store_true",
        help="Skip rows that contain unsupported Roman fragments and write invalid_rows.csv.",
    )
    parser.add_argument(
        "--max-samples",
        type=int,
        default=None,
        help="Limit generation to a deterministic subset of this many valid rows.",
    )
    parser.add_argument(
        "--enable-stroke-augmentation",
        action="store_true",
        help="Enable stroke pixel dropout and stroke patch dropout.",
    )
    parser.add_argument(
        "--augment-preset",
        choices=["light", "medium", "heavy"],
        default=None,
        help="Apply a predefined stroke augmentation preset. Explicit flags can still override it.",
    )
    parser.add_argument(
        "--stroke-threshold",
        type=int,
        default=220,
        help="Stroke threshold used to detect foreground pixels for augmentation.",
    )
    parser.add_argument(
        "--pixel-dropout-apply-prob",
        type=float,
        default=0.65,
        help="Probability of applying pixel-level stroke dropout to a sample.",
    )
    parser.add_argument(
        "--pixel-dropout-ratio-min",
        type=float,
        default=0.01,
        help="Minimum fraction of stroke pixels to erase when pixel dropout is applied.",
    )
    parser.add_argument(
        "--pixel-dropout-ratio-max",
        type=float,
        default=0.035,
        help="Maximum fraction of stroke pixels to erase when pixel dropout is applied.",
    )
    parser.add_argument(
        "--patch-dropout-apply-prob",
        type=float,
        default=0.8,
        help="Probability of applying patch-level stroke dropout to a sample.",
    )
    parser.add_argument(
        "--patch-count-min",
        type=int,
        default=1,
        help="Minimum number of stroke patches to drop when patch dropout is applied.",
    )
    parser.add_argument(
        "--patch-count-max",
        type=int,
        default=4,
        help="Maximum number of stroke patches to drop when patch dropout is applied.",
    )
    parser.add_argument(
        "--patch-size-min",
        type=int,
        default=2,
        help="Minimum side length of a dropped stroke patch.",
    )
    parser.add_argument(
        "--patch-size-max",
        type=int,
        default=8,
        help="Maximum side length of a dropped stroke patch.",
    )
    parser.add_argument(
        "--patch-shape",
        choices=["rectangle", "circle", "mixed"],
        default="rectangle",
        help="Shape used for stroke patch dropout.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root_dir = Path(__file__).resolve().parents[1]
    words_file = Path(args.words_file).resolve()
    output_dir = Path(args.output_dir).resolve()

    if not words_file.exists():
        raise FileNotFoundError(f"Words file not found: {words_file}")

    font_specs = resolve_font_specs(args.fonts, root_dir=root_dir)
    preset_config = get_augmentation_preset(args.augment_preset) if args.augment_preset else None
    augmentation_config = StrokeAugmentationConfig(
        enabled=args.enable_stroke_augmentation or preset_config is not None,
        threshold=preset_config.threshold if preset_config else args.stroke_threshold,
        pixel_dropout_apply_prob=(
            preset_config.pixel_dropout_apply_prob if preset_config else args.pixel_dropout_apply_prob
        ),
        pixel_dropout_ratio_min=(
            preset_config.pixel_dropout_ratio_min if preset_config else args.pixel_dropout_ratio_min
        ),
        pixel_dropout_ratio_max=(
            preset_config.pixel_dropout_ratio_max if preset_config else args.pixel_dropout_ratio_max
        ),
        patch_dropout_apply_prob=(
            preset_config.patch_dropout_apply_prob if preset_config else args.patch_dropout_apply_prob
        ),
        patch_count_min=preset_config.patch_count_min if preset_config else args.patch_count_min,
        patch_count_max=preset_config.patch_count_max if preset_config else args.patch_count_max,
        patch_size_min=preset_config.patch_size_min if preset_config else args.patch_size_min,
        patch_size_max=preset_config.patch_size_max if preset_config else args.patch_size_max,
        patch_shape=preset_config.patch_shape if preset_config else args.patch_shape,
    )

    stats = generate_dataset(
        words_file=words_file,
        font_specs=font_specs,
        output_dir=output_dir,
        seed=args.seed,
        canvas_width=args.canvas_width,
        canvas_height=args.canvas_height,
        padding_percentage=args.padding_percentage,
        skip_invalid=args.skip_invalid,
        max_samples=args.max_samples,
        augmentation_config=augmentation_config,
    )

    print(
        "Finished dataset generation: "
        f"{stats['valid_rows']} valid rows, "
        f"{stats['invalid_rows']} invalid rows, "
        f"{stats['train_rows']} train, "
        f"{stats['validation_rows']} validation."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
