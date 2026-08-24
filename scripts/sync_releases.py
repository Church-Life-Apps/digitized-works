#!/usr/bin/env python3
"""Build a validated catalog from the latest stable GitHub releases."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import shutil
import subprocess
import sys
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "catalog" / "sources.json"
DEFAULT_DISCUSSIONS = ROOT / ".cache" / "release-discussions.json"
USER_AGENT = "digitized-works-release-sync/1.0"


class SyncError(RuntimeError):
    pass


def request_json(url: str, token: str | None) -> dict:
    headers = {"Accept": "application/vnd.github+json", "User-Agent": USER_AGENT}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.load(response)
    except (urllib.error.URLError, json.JSONDecodeError) as exc:
        raise SyncError(f"GitHub request failed for {url}: {exc}") from exc


def download(url: str, destination: pathlib.Path, token: str | None) -> None:
    headers = {"Accept": "application/octet-stream", "User-Agent": USER_AGENT}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".partial")
    try:
        with urllib.request.urlopen(request, timeout=120) as response, temporary.open("wb") as output:
            shutil.copyfileobj(response, output)
        temporary.replace(destination)
    except urllib.error.URLError as exc:
        temporary.unlink(missing_ok=True)
        raise SyncError(f"Download failed for {url}: {exc}") from exc


def validate_pdf(path: pathlib.Path) -> dict:
    data = path.read_bytes()
    if len(data) < 1024 or not data.startswith(b"%PDF-"):
        raise SyncError(f"Invalid PDF signature or size: {path.name}")
    if b"%%EOF" not in data[-4096:]:
        raise SyncError(f"Missing PDF end marker: {path.name}")

    result = subprocess.run(
        ["pdfinfo", str(path)],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise SyncError(f"pdfinfo rejected {path.name}: {result.stderr.strip()}")
    fields = {}
    for line in result.stdout.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            fields[key.strip()] = value.strip()
    pages = int(fields.get("Pages", "0"))
    if pages < 1:
        raise SyncError(f"No pages found in {path.name}")
    return {
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "pages": pages,
    }


def latest_release(repository: str, token: str | None) -> dict:
    url = f"https://api.github.com/repos/{repository}/releases/latest"
    release = request_json(url, token)
    if release.get("draft") or release.get("prerelease"):
        raise SyncError(f"GitHub returned a non-stable release for {repository}")
    if not release.get("tag_name") or not release.get("published_at"):
        raise SyncError(f"Incomplete release metadata for {repository}")
    return release


def sync(
    config_path: pathlib.Path,
    output: pathlib.Path,
    cache: pathlib.Path,
    discussions_path: pathlib.Path = DEFAULT_DISCUSSIONS,
) -> dict:
    config = json.loads(config_path.read_text(encoding="utf-8"))
    discussions = {}
    if discussions_path.exists():
        discussions = json.loads(discussions_path.read_text(encoding="utf-8"))
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    output_pdfs = output / "pdfs"
    output_pdfs.mkdir(parents=True, exist_ok=True)
    checked_at = dt.datetime.now(dt.UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    generated_works = []
    for work in config["works"]:
        release = latest_release(work["repository"], token)
        assets = {asset["name"]: asset for asset in release.get("assets", [])}
        generated_documents = []

        for document in work["documents"]:
            asset_name = document["asset"].replace("{tag}", release["tag_name"])
            if asset_name not in assets:
                raise SyncError(
                    f"Expected {asset_name} in {work['repository']} release {release['tag_name']}"
                )
            asset = assets[asset_name]
            cached = cache / work["id"] / release["tag_name"] / asset_name
            if not cached.exists() or cached.stat().st_size != asset["size"]:
                download(asset["url"], cached, token)
            verification = validate_pdf(cached)
            destination = output_pdfs / work["id"] / asset_name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(cached, destination)
            generated_documents.append(
                {
                    **document,
                    "asset": asset_name,
                    **verification,
                    "pdf": f"pdfs/{work['id']}/{asset_name}",
                    "releaseAssetUrl": asset["browser_download_url"],
                }
            )

        generated_work = {
                **{key: value for key, value in work.items() if key != "documents"},
                "documents": generated_documents,
                "release": {
                    "tag": release["tag_name"],
                    "name": release.get("name") or release["tag_name"],
                    "publishedAt": release["published_at"],
                    "url": release["html_url"],
                },
                "freshness": {"state": "current", "checkedAt": checked_at},
            }
        discussion = discussions.get(work["id"])
        if discussion and discussion.get("tag") == release["tag_name"]:
            generated_work["reviewDiscussionUrl"] = discussion["url"]
        generated_works.append(generated_work)

    catalog = {
        "schemaVersion": 1,
        "generatedAt": checked_at,
        "site": config["site"],
        "works": generated_works,
        "plannedWorks": config.get("plannedWorks", []),
    }
    (output / "catalog.json").write_text(json.dumps(catalog, indent=2) + "\n", encoding="utf-8")
    return catalog


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=pathlib.Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=pathlib.Path, required=True)
    parser.add_argument("--cache", type=pathlib.Path, default=ROOT / ".cache" / "releases")
    parser.add_argument("--discussions", type=pathlib.Path, default=DEFAULT_DISCUSSIONS)
    args = parser.parse_args()
    try:
        catalog = sync(args.config, args.output, args.cache, args.discussions)
    except (SyncError, OSError, subprocess.SubprocessError, ValueError) as exc:
        print(f"sync failed: {exc}", file=sys.stderr)
        return 1
    documents = sum(len(work["documents"]) for work in catalog["works"])
    print(f"validated {documents} PDFs across {len(catalog['works'])} works")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
