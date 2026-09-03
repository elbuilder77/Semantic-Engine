#!/usr/bin/env python3
"""Check whether a specific crate version is already published on crates.io."""

import argparse
from collections.abc import Callable
from http.client import HTTPResponse
from pathlib import Path
import tomllib
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


USER_AGENT = (
    "Semantic-Engine-release-workflow/1.0 "
    "(https://github.com/elbuilder77/Semantic-Engine)"
)
MISSING_EXIT_CODE = 3
ROOT = Path(__file__).resolve().parents[1]


def local_crate_version() -> str:
    with (ROOT / "core_rs" / "Cargo.toml").open("rb") as handle:
        return tomllib.load(handle)["package"]["version"]


def publication_status(
    crate: str,
    version: str,
    opener: Callable[..., HTTPResponse] = urlopen,
) -> bool:
    url = f"https://crates.io/api/v1/crates/{crate}/{version}"
    request = Request(url, headers={"User-Agent": USER_AGENT})

    try:
        with opener(request, timeout=20) as response:
            status = response.status
    except HTTPError as error:
        status = error.code
    except URLError as error:
        raise RuntimeError(f"crates.io request failed: {error.reason}") from error

    if status == 200:
        return True
    if status == 404:
        return False
    raise RuntimeError(f"crates.io returned unexpected HTTP {status}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--crate", default="jas_vector_core")
    parser.add_argument("--version", default=None)
    parser.add_argument("--allow-missing", action="store_true")
    args = parser.parse_args()

    version = args.version or local_crate_version()
    try:
        exists = publication_status(args.crate, version)
    except RuntimeError as error:
        parser.error(str(error))

    if exists:
        print(f"{args.crate} {version} is already published on crates.io")
        return 0

    print(f"{args.crate} {version} is available for publication on crates.io")
    return 0 if args.allow_missing else MISSING_EXIT_CODE


if __name__ == "__main__":
    raise SystemExit(main())
