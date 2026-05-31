import argparse
import os
from pathlib import Path

from PIL import Image

SUPPORTED_INPUTS = {".webp", ".png", ".jpeg", ".jpg", ".bmp", ".gif"}


def convert_file(path: Path, target: Path, delete_original: bool) -> bool:
    if target.exists():
        if delete_original and path.suffix.lower() != ".jpg":
            path.unlink(missing_ok=True)
        return False

    target.parent.mkdir(parents=True, exist_ok=True)

    with Image.open(path) as img:
        rgb = img.convert("RGB")
        rgb.save(target, format="JPEG", quality=95)

    if delete_original:
        path.unlink(missing_ok=True)

    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Batch convert images to JPG (default: common formats -> JPG)."
    )
    parser.add_argument(
        "--root",
        default="dataset",
        help="Root directory to scan (default: dataset)",
    )
    parser.add_argument(
        "--output-root",
        default="dataset_new",
        help="Output root directory for JPGs (default: dataset_new)",
    )
    parser.add_argument(
        "--delete-original",
        action="store_true",
        help="Delete original files after conversion.",
    )
    parser.add_argument(
        "--formats",
        default="webp,png,jpeg,jpg,bmp,gif",
        help="Comma-separated input formats to convert (default: webp,png,jpeg,jpg,bmp,gif).",
    )

    args = parser.parse_args()
    root = Path(args.root)

    if not root.exists():
        print(f"Root directory not found: {root}")
        return 1

    delete_original = args.delete_original
    formats = {f".{fmt.strip().lower()}" for fmt in args.formats.split(",") if fmt.strip()}
    inputs = formats if formats else set(SUPPORTED_INPUTS)
    output_root = Path(args.output_root)

    converted = 0
    skipped = 0
    failed = 0

    for dirpath, _, filenames in os.walk(root):
        for filename in filenames:
            path = Path(dirpath) / filename
            suffix = path.suffix.lower()
            if suffix not in inputs:
                continue

            try:
                relative_path = path.relative_to(root)
                target = (output_root / relative_path).with_suffix(".jpg")
                if convert_file(path, target, delete_original):
                    converted += 1
                else:
                    skipped += 1
            except Exception as exc:
                failed += 1
                print(f"Failed: {path} -> {exc}")

    print(
        f"Done. Converted: {converted}, Skipped: {skipped}, Failed: {failed}"
    )
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
