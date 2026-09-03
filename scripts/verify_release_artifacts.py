#!/usr/bin/env python3
"""Inspect ses-core distributions before registry publication."""

import argparse
from pathlib import Path
import tarfile
import zipfile

from validate_release import validate


def verify_wheel(path: Path, expected_version: str) -> None:
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if "ses/__init__.py" not in names:
            raise ValueError(f"{path.name} does not contain the ses Python package")
        if not any(
            name.startswith("jas_vector_core/") and name.endswith((".so", ".pyd"))
            for name in names
        ):
            raise ValueError(f"{path.name} does not contain jas_vector_core")
        metadata_name = f"ses_core-{expected_version}.dist-info/METADATA"
        metadata = archive.read(metadata_name).decode("utf-8")
        if f"Version: {expected_version}" not in metadata:
            raise ValueError(f"{path.name} contains unexpected package metadata")


def verify_sdist(path: Path, expected_version: str) -> None:
    prefix = f"ses_core-{expected_version}/"
    required = {
        f"{prefix}LICENSE",
        f"{prefix}pyproject.toml",
        f"{prefix}core_rs/Cargo.toml",
        f"{prefix}core_rs/src/lib.rs",
        f"{prefix}ses/__init__.py",
    }
    with tarfile.open(path, "r:gz") as archive:
        missing = required.difference(archive.getnames())
    if missing:
        raise ValueError(f"{path.name} is missing: {', '.join(sorted(missing))}")


def verify(directory: Path, require_platforms: bool = False) -> None:
    ses_version, _ = validate()
    wheels = sorted(directory.glob(f"ses_core-{ses_version}-*.whl"))
    sdists = sorted(directory.glob(f"ses_core-{ses_version}.tar.gz"))
    if not wheels:
        raise ValueError("no ses-core wheels found")
    if len(sdists) != 1:
        raise ValueError(f"expected one ses-core sdist, found {len(sdists)}")

    for wheel in wheels:
        verify_wheel(wheel, ses_version)
    verify_sdist(sdists[0], ses_version)

    if require_platforms:
        filenames = [wheel.name for wheel in wheels]
        required_markers = ("manylinux", "win_amd64", "macosx")
        missing = [
            marker
            for marker in required_markers
            if not any(marker in filename for filename in filenames)
        ]
        if missing:
            raise ValueError(f"missing wheel platforms: {', '.join(missing)}")

    print(f"verified {len(wheels)} wheel(s) and {sdists[0].name}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    parser.add_argument("--require-platforms", action="store_true")
    args = parser.parse_args()
    try:
        verify(args.directory, args.require_platforms)
    except ValueError as error:
        parser.error(str(error))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
