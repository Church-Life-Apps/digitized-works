#!/usr/bin/env python3
"""Perform deterministic checks on a generated deployment."""

from __future__ import annotations

import json
import pathlib
import sys


def fail(message: str) -> None:
    raise SystemExit(f"verification failed: {message}")


def main() -> int:
    root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else "dist")
    required = [
        root / "index.html",
        root / "read" / "index.html",
        root / "assets" / "app.js",
        root / "assets" / "reader.js",
        root / "assets" / "styles.css",
        root / "vendor" / "pdfjs" / "web" / "viewer.html",
        root / "catalog.json",
        root / ".nojekyll",
    ]
    missing = [str(path.relative_to(root)) for path in required if not path.exists()]
    if missing:
        fail(f"missing files: {', '.join(missing)}")

    catalog = json.loads((root / "catalog.json").read_text(encoding="utf-8"))
    if catalog.get("schemaVersion") != 1:
        fail("unsupported catalog schema")
    if len(catalog.get("works", [])) != 3:
        fail("expected exactly three initial works")
    review_statuses = {work["id"]: work.get("reviewStatus") for work in catalog["works"]}
    expected_review_statuses = {
        "alford-greek-testament": "ready",
        "govett-parables": "ready",
        "govett-revelation": "in-progress",
    }
    if review_statuses != expected_review_statuses:
        fail(f"unexpected review statuses: {review_statuses}")
    for work in catalog["works"]:
        if work["reviewStatus"] == "ready":
            if "reviewDiscussionUrl" not in work:
                fail(f"review discussion missing for {work['id']}")
            if not work["reviewDiscussionUrl"].startswith(
                "https://github.com/Church-Life-Apps/digitized-works/discussions/"
            ):
                fail(f"invalid review discussion URL for {work['id']}")
        elif "reviewDiscussionUrl" in work:
            fail(f"non-reviewable work has a review discussion: {work['id']}")
    planned_works = catalog.get("plannedWorks", [])
    if len(planned_works) != 28:
        fail(f"expected 28 upcoming works, found {len(planned_works)}")
    if len({work["id"] for work in planned_works}) != 28:
        fail("upcoming work IDs must be unique")
    unreleased = [work for work in planned_works if work.get("projectStatus") == "in-progress"]
    if [work["id"] for work in unreleased] != ["conybeare-howson-life-epistles-st-paul"]:
        fail(f"unexpected unreleased works: {[work['id'] for work in unreleased]}")
    documents = [document for work in catalog["works"] for document in work["documents"]]
    if len(documents) != 6:
        fail("expected six initial PDFs")
    for document in documents:
        path = root / document["pdf"]
        if not path.exists():
            fail(f"catalog PDF missing: {document['pdf']}")
        if path.stat().st_size != document["bytes"]:
            fail(f"catalog size mismatch: {document['pdf']}")
        if document["pages"] < 1 or len(document["sha256"]) != 64:
            fail(f"invalid verification metadata: {document['pdf']}")

    if "FRESHNESS_LIMIT_MS = 12 * 60 * 60 * 1000" not in (root / "assets" / "app.js").read_text():
        fail("home-page freshness guard missing")
    if "FRESHNESS_LIMIT_MS = 12 * 60 * 60 * 1000" not in (root / "assets" / "reader.js").read_text():
        fail("reader freshness guard missing")
    print(f"verified {len(catalog['works'])} works and {len(documents)} PDFs")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
