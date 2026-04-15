#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert a generated Manchu image dataset into Hugging Face Viewer-friendly Parquet shards."
    )
    parser.add_argument(
        "--dataset-dir",
        required=True,
        help="Input dataset directory, e.g. output-manchu.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Output directory for the Parquet dataset, e.g. output-manchu-parquet.",
    )
    parser.add_argument(
        "--rows-per-shard",
        type=int,
        default=5000,
        help="Number of rows per Parquet shard.",
    )
    return parser.parse_args()


def validate_dataset_dir(dataset_dir: Path) -> None:
    expected_paths = [
        dataset_dir / "train" / "metadata.csv",
        dataset_dir / "validation" / "metadata.csv",
        dataset_dir / "summary.json",
    ]
    missing = [str(path) for path in expected_paths if not path.exists()]
    if missing:
        raise FileNotFoundError(
            "Dataset directory does not look complete. Missing expected files:\n"
            + "\n".join(missing)
        )


def load_split_examples(dataset_dir: Path, split_name: str) -> list[dict[str, object]]:
    split_dir = dataset_dir / split_name
    metadata_path = split_dir / "metadata.csv"
    examples: list[dict[str, object]] = []

    with metadata_path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            relative_image_path = row["im"]
            image_path = split_dir / relative_image_path
            if not image_path.exists():
                raise FileNotFoundError(f"Missing image referenced in {metadata_path}: {image_path}")

            examples.append(
                {
                    "im": {
                        "bytes": image_path.read_bytes(),
                        "path": relative_image_path,
                    },
                    "roman": row["roman"],
                    "manchu": row["manchu"],
                }
            )

    return examples


def write_readme(output_dir: Path) -> None:
    readme_path = output_dir / "README.md"
    if readme_path.exists():
        return
    readme_path.write_text(
        "# Manchu Augmented Dataset\n\n"
        "This dataset was exported as Parquet shards for Hugging Face Dataset Viewer compatibility.\n",
        encoding="utf-8",
    )


def main() -> int:
    from datasets import Dataset, Features, Image, Value

    args = parse_args()
    dataset_dir = Path(args.dataset_dir).resolve()
    output_dir = Path(args.output_dir).resolve()
    validate_dataset_dir(dataset_dir)

    if args.rows_per_shard <= 0:
        raise ValueError("--rows-per-shard must be positive.")

    features = Features(
        {
            "im": Image(),
            "roman": Value("string"),
            "manchu": Value("string"),
        }
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    write_readme(output_dir)

    for split_name in ("train", "validation"):
        examples = load_split_examples(dataset_dir, split_name)
        dataset = Dataset.from_list(examples, features=features)
        shard_count = max(1, math.ceil(len(dataset) / args.rows_per_shard))

        for shard_index in range(shard_count):
            shard = dataset.shard(num_shards=shard_count, index=shard_index, contiguous=True)
            shard_name = f"{split_name}-{shard_index:05d}-of-{shard_count:05d}.parquet"
            shard_path = output_dir / shard_name
            shard.to_parquet(str(shard_path))

        print(f"{split_name}: {len(dataset)} rows -> {shard_count} parquet shard(s)")

    print(f"Parquet dataset written to: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
