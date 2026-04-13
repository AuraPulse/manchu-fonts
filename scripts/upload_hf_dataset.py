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
    parser.add_argument(
        "--batch",
        choices=["split", "all"],
        default="split",
        help="Upload strategy. 'split' uploads summary/train/validation separately.",
    )
    return parser.parse_args()


def validate_dataset_dir(dataset_dir: Path) -> None:
    if not dataset_dir.exists():
        raise FileNotFoundError(f"Dataset directory not found: {dataset_dir}")
    if not dataset_dir.is_dir():
        raise NotADirectoryError(f"Dataset path is not a directory: {dataset_dir}")

    layout = detect_dataset_layout(dataset_dir)
    if layout in {"image", "arrow", "parquet"}:
        return
    raise FileNotFoundError(
        "Dataset directory is neither a generated image dataset, a Hugging Face Arrow dataset saved with "
        "datasets.save_to_disk(), nor a Viewer-friendly Parquet dataset."
    )


def detect_dataset_layout(dataset_dir: Path) -> str:
    image_expected_paths = [
        dataset_dir / "train" / "metadata.csv",
        dataset_dir / "validation" / "metadata.csv",
        dataset_dir / "summary.json",
    ]
    if all(path.exists() for path in image_expected_paths):
        return "image"

    arrow_expected_paths = [
        dataset_dir / "dataset_dict.json",
        dataset_dir / "train",
        dataset_dir / "validation",
    ]
    if all(path.exists() for path in arrow_expected_paths):
        return "arrow"

    parquet_files = list(dataset_dir.glob("*.parquet"))
    if parquet_files and any("train-" in path.name for path in parquet_files):
        return "parquet"

    return "unknown"


def join_repo_path(base: str, child: str) -> str:
    normalized_base = "" if base in {".", ""} else base.strip("/")
    normalized_child = child.strip("/")
    if not normalized_base:
        return normalized_child
    if not normalized_child:
        return normalized_base
    return f"{normalized_base}/{normalized_child}"


def upload_folder_maybe_large(
    *,
    api,
    local_dir: Path,
    repo_id: str,
    revision: str,
    repo_private: bool,
    repo_path: str,
    exclude: list[str],
    mode: str,
    commit_message: str,
) -> str:
    upload_large_folder = getattr(api, "upload_large_folder", None)
    use_large_upload = mode == "large" or (mode == "auto" and callable(upload_large_folder))

    if use_large_upload:
        supported_params = set(inspect.signature(upload_large_folder).parameters)
        large_kwargs = {
            "repo_id": repo_id,
            "repo_type": "dataset",
            "folder_path": str(local_dir),
            "revision": revision,
            "private": repo_private,
            "ignore_patterns": exclude,
        }

        if "path_in_repo" in supported_params:
            large_kwargs["path_in_repo"] = repo_path
        elif repo_path not in {".", ""}:
            if mode == "large":
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
            return "upload_large_folder"

    result = api.upload_folder(
        repo_id=repo_id,
        repo_type="dataset",
        folder_path=str(local_dir),
        path_in_repo=repo_path,
        revision=revision,
        commit_message=commit_message,
        ignore_patterns=exclude,
    )
    return f"upload_folder:{result.oid}"


def upload_file(
    *,
    api,
    local_file: Path,
    repo_id: str,
    revision: str,
    repo_path: str,
    commit_message: str,
) -> str:
    result = api.upload_file(
        repo_id=repo_id,
        repo_type="dataset",
        path_or_fileobj=str(local_file),
        path_in_repo=repo_path,
        revision=revision,
        commit_message=commit_message,
    )
    return result.oid


def upload_root_files(
    *,
    api,
    dataset_dir: Path,
    repo_id: str,
    revision: str,
    path_in_repo: str,
    commit_message: str,
    include_files: list[str],
) -> list[str]:
    uploaded_parts: list[str] = []
    for file_name in include_files:
        local_file = dataset_dir / file_name
        if not local_file.exists():
            continue
        commit_id = upload_file(
            api=api,
            local_file=local_file,
            repo_id=repo_id,
            revision=revision,
            repo_path=join_repo_path(path_in_repo, file_name),
            commit_message=f"{commit_message} ({file_name})",
        )
        uploaded_parts.append(f"{file_name}:{commit_id}")
    return uploaded_parts


def upload_parquet_split_files(
    *,
    api,
    dataset_dir: Path,
    repo_id: str,
    revision: str,
    path_in_repo: str,
    commit_message: str,
    split_name: str,
) -> list[str]:
    uploaded_parts: list[str] = []
    split_files = sorted(dataset_dir.glob(f"{split_name}-*.parquet"))
    for split_file in split_files:
        commit_id = upload_file(
            api=api,
            local_file=split_file,
            repo_id=repo_id,
            revision=revision,
            repo_path=join_repo_path(path_in_repo, split_file.name),
            commit_message=f"{commit_message} ({split_file.name})",
        )
        uploaded_parts.append(f"{split_file.name}:{commit_id}")
    return uploaded_parts


def main() -> int:
    from huggingface_hub import HfApi

    args = parse_args()
    dataset_dir = Path(args.dataset_dir).resolve()
    validate_dataset_dir(dataset_dir)
    layout = detect_dataset_layout(dataset_dir)

    if not args.token:
        raise ValueError("Missing Hugging Face token. Pass --token or set HF_TOKEN.")

    api = HfApi(token=args.token)
    api.create_repo(
        repo_id=args.repo_id,
        repo_type="dataset",
        private=args.repo_private,
        exist_ok=True,
    )

    if args.batch == "all":
        mode_used = upload_folder_maybe_large(
            api=api,
            local_dir=dataset_dir,
            repo_id=args.repo_id,
            revision=args.revision,
            repo_private=args.repo_private,
            repo_path=args.path_in_repo,
            exclude=args.exclude,
            mode=args.mode,
            commit_message=args.commit_message,
        )
        print(f"Uploaded dataset from: {dataset_dir}")
        print(f"Repo: https://huggingface.co/datasets/{args.repo_id}")
        print(f"Upload mode: {mode_used}")
        print(f"Detected layout: {layout}")
        return 0

    uploaded_parts: list[str] = []

    if layout == "image":
        uploaded_parts.extend(
            upload_root_files(
                api=api,
                dataset_dir=dataset_dir,
                repo_id=args.repo_id,
                revision=args.revision,
                path_in_repo=args.path_in_repo,
                commit_message=args.commit_message,
                include_files=["summary.json", "invalid_rows.csv"],
            )
        )
    elif layout == "arrow":
        uploaded_parts.extend(
            upload_root_files(
                api=api,
                dataset_dir=dataset_dir,
                repo_id=args.repo_id,
                revision=args.revision,
                path_in_repo=args.path_in_repo,
                commit_message=args.commit_message,
                include_files=["dataset_dict.json", "state.json", "dataset_info.json"],
            )
        )
    elif layout == "parquet":
        uploaded_parts.extend(
            upload_root_files(
                api=api,
                dataset_dir=dataset_dir,
                repo_id=args.repo_id,
                revision=args.revision,
                path_in_repo=args.path_in_repo,
                commit_message=args.commit_message,
                include_files=["README.md"],
            )
        )

    if layout == "parquet":
        for split_name in ("train", "validation"):
            uploaded_parts.extend(
                upload_parquet_split_files(
                    api=api,
                    dataset_dir=dataset_dir,
                    repo_id=args.repo_id,
                    revision=args.revision,
                    path_in_repo=args.path_in_repo,
                    commit_message=args.commit_message,
                    split_name=split_name,
                )
            )
    else:
        for split_name in ("train", "validation"):
            split_dir = dataset_dir / split_name
            split_mode = upload_folder_maybe_large(
                api=api,
                local_dir=split_dir,
                repo_id=args.repo_id,
                revision=args.revision,
                repo_private=args.repo_private,
                repo_path=join_repo_path(args.path_in_repo, split_name),
                exclude=args.exclude,
                mode=args.mode,
                commit_message=f"{args.commit_message} ({split_name})",
            )
            uploaded_parts.append(f"{split_name}:{split_mode}")

    print(f"Uploaded dataset from: {dataset_dir}")
    print(f"Repo: https://huggingface.co/datasets/{args.repo_id}")
    print("Upload strategy: split")
    print(f"Detected layout: {layout}")
    for part in uploaded_parts:
        print(f"Part: {part}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
