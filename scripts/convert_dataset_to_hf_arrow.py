#!/usr/bin/env python3

from __future__ import annotations

import argparse
import csv
from pathlib import Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert a generated Manchu image dataset into a self-contained Hugging Face Arrow dataset."
    )
    parser.add_argument(
        "--dataset-dir",
        required=True,
        help="Input dataset directory, e.g. output-manchu.",
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Output directory for the Arrow dataset, e.g. output-manchu-arrow.",
    )
    parser.add_argument(
        "--max-shard-size",
        default="500MB",
        help="Maximum shard size passed to datasets.save_to_disk().",
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
                    "image": {
                        "bytes": image_path.read_bytes(),
                        "path": relative_image_path,
                    },
                    "file_name": relative_image_path,
                    "roman": row["roman"],
                    "manchu": row["manchu"],
                    "font_id": Path(relative_image_path).parent.name,
                }
            )

    return examples


def main() -> int:
    from datasets import Dataset, DatasetDict, Features, Image, Value

    args = parse_args()
    dataset_dir = Path(args.dataset_dir).resolve()
    output_dir = Path(args.output_dir).resolve()
    validate_dataset_dir(dataset_dir)

    features = Features(
        {
            "image": Image(),
            "file_name": Value("string"),
            "roman": Value("string"),
            "manchu": Value("string"),
            "font_id": Value("string"),
        }
    )

    split_datasets: dict[str, Dataset] = {}
    for split_name in ("train", "validation"):
        examples = load_split_examples(dataset_dir, split_name)
        split_datasets[split_name] = Dataset.from_list(examples, features=features)

    dataset = DatasetDict(split_datasets)
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    dataset.save_to_disk(str(output_dir), max_shard_size=args.max_shard_size)

    print(f"Arrow dataset written to: {output_dir}")
    for split_name, split_dataset in dataset.items():
        print(f"{split_name}: {len(split_dataset)} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
