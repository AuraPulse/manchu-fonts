#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import json
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
    canvas_height: int,
    padding_percentage: float,
) -> Image.Image:
    if canvas_height <= 0:
        raise ValueError("canvas_height must be positive.")
    if not 0 <= padding_percentage < 0.5:
        raise ValueError("padding_percentage must be in [0, 0.5).")

    content = render_tight_content(text, font)
    aspect_ratio = content.width / content.height

    canvas_width = max(1, round(canvas_height * aspect_ratio))
    inner_height = max(1, round(canvas_height * (1 - padding_percentage * 2)))
    inner_width = max(1, round(inner_height * aspect_ratio))
    canvas_width = max(canvas_width, inner_width)

    resized_inner = content.resize((inner_width, inner_height), RESAMPLE_LANCZOS).convert("RGB")
    padded_image = Image.new("RGB", (canvas_width, canvas_height), "white")

    padding_x = round((canvas_width - inner_width) / 2)
    padding_y = round((canvas_height - inner_height) / 2)
    padded_image.paste(resized_inner, (padding_x, padding_y))

    return padded_image


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
    canvas_height: int,
    padding_percentage: float,
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
        "canvas_height": canvas_height,
        "padding_percentage": padding_percentage,
        "total_samples": len(samples),
        "invalid_samples": len(invalid_rows),
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
    canvas_height: int,
    padding_percentage: float,
    skip_invalid: bool,
) -> dict[str, int]:
    source_rows = read_source_rows(words_file)
    converted_rows, invalid_rows = convert_rows(source_rows, skip_invalid=skip_invalid)
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
                canvas_height=canvas_height,
                padding_percentage=padding_percentage,
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
        canvas_height=canvas_height,
        padding_percentage=padding_percentage,
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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root_dir = Path(__file__).resolve().parents[1]
    words_file = Path(args.words_file).resolve()
    output_dir = Path(args.output_dir).resolve()

    if not words_file.exists():
        raise FileNotFoundError(f"Words file not found: {words_file}")

    font_specs = resolve_font_specs(args.fonts, root_dir=root_dir)

    stats = generate_dataset(
        words_file=words_file,
        font_specs=font_specs,
        output_dir=output_dir,
        seed=args.seed,
        canvas_height=args.canvas_height,
        padding_percentage=args.padding_percentage,
        skip_invalid=args.skip_invalid,
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
