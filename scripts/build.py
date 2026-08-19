#!/usr/bin/env python3
"""Create the complete static GitHub Pages deployment."""

from __future__ import annotations

import argparse
import pathlib
import shutil
import subprocess
import sys
import urllib.request
import zipfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
PDFJS_VERSION = "6.2.108"
PDFJS_URL = f"https://github.com/mozilla/pdf.js/releases/download/v{PDFJS_VERSION}/pdfjs-{PDFJS_VERSION}-dist.zip"


def install_pdfjs(cache: pathlib.Path, destination: pathlib.Path) -> None:
    archive = cache / f"pdfjs-{PDFJS_VERSION}-dist.zip"
    extracted = cache / f"pdfjs-{PDFJS_VERSION}"
    cache.mkdir(parents=True, exist_ok=True)
    if not archive.exists():
        print(f"downloading PDF.js {PDFJS_VERSION}")
        urllib.request.urlretrieve(PDFJS_URL, archive)
    if not extracted.exists():
        temporary = cache / f"pdfjs-{PDFJS_VERSION}.partial"
        shutil.rmtree(temporary, ignore_errors=True)
        temporary.mkdir()
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(temporary)
        temporary.replace(extracted)
    shutil.copytree(extracted, destination, dirs_exist_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=pathlib.Path, default=ROOT / "dist")
    args = parser.parse_args()
    output = args.output.resolve()
    shutil.rmtree(output, ignore_errors=True)
    shutil.copytree(ROOT / "site", output)
    install_pdfjs(ROOT / ".cache" / "pdfjs", output / "vendor" / "pdfjs")
    command = [
        sys.executable,
        str(ROOT / "scripts" / "sync_releases.py"),
        "--output",
        str(output),
    ]
    result = subprocess.run(command, cwd=ROOT, check=False)
    if result.returncode:
        return result.returncode
    (output / ".nojekyll").touch()
    print(f"built {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

