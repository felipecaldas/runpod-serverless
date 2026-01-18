from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path


UTF8_BOM = b"\xef\xbb\xbf"


@dataclass(frozen=True)
class NormalizeResult:
    scanned: int
    changed: int
    skipped_binary: int


_TEXT_EXTENSIONS: set[str] = {
    ".sh",
    ".py",
    ".yaml",
    ".yml",
    ".json",
    ".md",
    ".txt",
    ".csv",
    ".toml",
    ".ini",
    ".cfg",
}

_TEXT_FILENAMES: set[str] = {
    "Dockerfile",
    "Dockerfile.custom",
    ".gitattributes",
}


def _is_probably_binary(content: bytes) -> bool:
    sample = content[:8192]
    return b"\x00" in sample


def normalize_file(path: Path, *, check_only: bool) -> bool:
    """Normalize a file to UTF-8 (no BOM) and LF line endings.

    Returns True if the file would be/was changed.
    """

    original = path.read_bytes()

    if _is_probably_binary(original):
        return False

    updated = original

    if updated.startswith(UTF8_BOM):
        updated = updated[len(UTF8_BOM) :]

    updated = updated.replace(b"\r\n", b"\n").replace(b"\r", b"\n")

    if updated == original:
        return False

    if not check_only:
        path.write_bytes(updated)

    return True


def normalize_paths(paths: list[Path], *, check_only: bool) -> NormalizeResult:
    """Normalize all eligible text files under the given paths."""

    scanned = 0
    changed = 0
    skipped_binary = 0

    for input_path in paths:
        if not input_path.exists():
            continue

        candidates: list[Path]
        if input_path.is_dir():
            candidates = [p for p in input_path.rglob("*") if p.is_file()]
        else:
            candidates = [input_path]

        for file_path in candidates:
            rel = str(file_path).lower()
            if "\\.git\\" in rel or "\\__pycache__\\" in rel:
                continue

            if file_path.name in _TEXT_FILENAMES or file_path.suffix.lower() in _TEXT_EXTENSIONS:
                scanned += 1
                before = file_path.read_bytes()

                if _is_probably_binary(before):
                    skipped_binary += 1
                    continue

                if normalize_file(file_path, check_only=check_only):
                    changed += 1

    return NormalizeResult(scanned=scanned, changed=changed, skipped_binary=skipped_binary)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="Check whether normalization is needed; do not modify files.",
    )
    parser.add_argument(
        "paths",
        nargs="*",
        default=["src", "scripts", "docs", "workflows", "schemas", "Dockerfile.custom", "build_custom.sh", ".gitattributes"],
    )

    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parents[1]
    input_paths = [repo_root / p for p in args.paths]

    result = normalize_paths(input_paths, check_only=args.check)

    print(
        f"normalize_line_endings: scanned={result.scanned} changed={result.changed} skipped_binary={result.skipped_binary}"
    )

    if args.check and result.changed > 0:
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
