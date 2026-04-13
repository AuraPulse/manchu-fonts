#!/usr/bin/env python3

from __future__ import annotations

import argparse
import inspect
import os
from pathlib import Path

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Upload a generated Manchu dataset folder to a Hugging Face dataset repository."
    )
    parser.add_argument(
        "--dataset-dir",
        required=True,
        help="Local dataset directory to upload, e.g. dataset/hf-all-augmented.",
    )
    parser.add_argument(
        "--repo-id",
        required=True,
        help="Hugging Face dataset repo id, e.g. your-name/manchu-hf-all-augmented.",
    )
    parser.add_argument(
        "--token",
        default=os.environ.get("HF_TOKEN") or os.environ.get("HUGGINGFACE_TOKEN"),
        help="Hugging Face token. Defaults to HF_TOKEN or HUGGINGFACE_TOKEN.",
    )
    parser.add_argument(
        "--repo-private",
        action="store_true",
        help="Create the dataset repo as private if it does not already exist.",
    )
    parser.add_argument(
        "--revision",
        default="main",
        help="Branch to upload to. Defaults to main.",
    )
    parser.add_argument(
        "--commit-message",
        default="Upload Manchu dataset",
        help="Commit message used for the upload.",
    )
    parser.add_argument(
        "--path-in-repo",
        default=".",
        help="Target path inside the repo. Defaults to repository root.",
    )
    parser.add_argument(
        "--exclude",
        nargs="*",
        default=[".DS_Store", "**/.DS_Store"],
        help="Optional glob patterns to exclude from upload.",
    )
    parser.add_argument(
        "--mode",
        choices=["auto", "large", "regular"],
        default="regular",
        help="Upload mode. 'regular' is the safest default. 'auto' prefers upload_large_folder when available.",
    )
    return parser.parse_args()


def validate_dataset_dir(dataset_dir: Path) -> None:
    if not dataset_dir.exists():
        raise FileNotFoundError(f"Dataset directory not found: {dataset_dir}")
    if not dataset_dir.is_dir():
        raise NotADirectoryError(f"Dataset path is not a directory: {dataset_dir}")

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


def main() -> int:
    from huggingface_hub import HfApi

    args = parse_args()
    dataset_dir = Path(args.dataset_dir).resolve()
    validate_dataset_dir(dataset_dir)

    if not args.token:
        raise ValueError("Missing Hugging Face token. Pass --token or set HF_TOKEN.")

    api = HfApi(token=args.token)
    api.create_repo(
        repo_id=args.repo_id,
        repo_type="dataset",
        private=args.repo_private,
        exist_ok=True,
    )

    upload_large_folder = getattr(api, "upload_large_folder", None)
    use_large_upload = args.mode == "large" or (args.mode == "auto" and callable(upload_large_folder))

    if use_large_upload:
        supported_params = set(inspect.signature(upload_large_folder).parameters)
        large_kwargs = {
            "repo_id": args.repo_id,
            "repo_type": "dataset",
            "folder_path": str(dataset_dir),
            "revision": args.revision,
            "private": args.repo_private,
            "ignore_patterns": args.exclude,
        }

        if "path_in_repo" in supported_params:
            large_kwargs["path_in_repo"] = args.path_in_repo
        elif args.path_in_repo not in {".", ""}:
            if args.mode == "large":
                raise ValueError(
                    "This version of huggingface_hub does not support --path-in-repo with "
                    "upload_large_folder(). Upgrade huggingface_hub or use --mode regular."
                )
            use_large_upload = False

        if use_large_upload:
            filtered_large_kwargs = {
                key: value for key, value in large_kwargs.items() if key in supported_params
            }
            upload_large_folder(**filtered_large_kwargs)
            print(f"Uploaded dataset from: {dataset_dir}")
            print(f"Repo: https://huggingface.co/datasets/{args.repo_id}")
            print("Upload mode: upload_large_folder")
            return 0

    result = api.upload_folder(
        repo_id=args.repo_id,
        repo_type="dataset",
        folder_path=str(dataset_dir),
        path_in_repo=args.path_in_repo,
        revision=args.revision,
        commit_message=args.commit_message,
        ignore_patterns=args.exclude,
    )

    print(f"Uploaded dataset from: {dataset_dir}")
    print(f"Repo: https://huggingface.co/datasets/{args.repo_id}")
    print("Upload mode: upload_folder")
    print(f"Commit: {result.oid}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
