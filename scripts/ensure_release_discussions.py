#!/usr/bin/env python3
"""Create or reuse one public review discussion for each review-ready release."""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import urllib.error
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "catalog" / "sources.json"
DEFAULT_OUTPUT = ROOT / ".cache" / "release-discussions.json"
GRAPHQL_URL = "https://api.github.com/graphql"
SOURCE_API = "https://api.github.com/repos"
TARGET_OWNER = "Church-Life-Apps"
TARGET_REPOSITORY = "digitized-works"
CATEGORY_NAME = "General"
USER_AGENT = "digitized-works-release-discussions/1.0"


class DiscussionError(RuntimeError):
    pass


def request_json(url: str, token: str, data: dict | None = None) -> dict:
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "User-Agent": USER_AGENT,
        "X-GitHub-Api-Version": "2022-11-28",
    }
    body = None
    if data is not None:
        headers["Content-Type"] = "application/json"
        body = json.dumps(data).encode()
    request = urllib.request.Request(url, headers=headers, data=body)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.load(response)
    except (urllib.error.URLError, json.JSONDecodeError) as exc:
        raise DiscussionError(f"GitHub request failed for {url}: {exc}") from exc
    if isinstance(result, dict) and result.get("errors"):
        messages = "; ".join(error.get("message", "unknown GraphQL error") for error in result["errors"])
        raise DiscussionError(messages)
    return result


def graphql(token: str, query: str, variables: dict | None = None) -> dict:
    result = request_json(
        GRAPHQL_URL,
        token,
        {"query": query, "variables": variables or {}},
    )
    return result["data"]


def latest_release(repository: str, token: str) -> dict:
    release = request_json(f"{SOURCE_API}/{repository}/releases/latest", token)
    if release.get("draft") or release.get("prerelease"):
        raise DiscussionError(f"Latest release for {repository} is not stable")
    return release


def repository_context(token: str) -> tuple[str, str, dict[str, str]]:
    data = graphql(
        token,
        """
        query RepositoryContext($owner: String!, $name: String!) {
          repository(owner: $owner, name: $name) {
            id
            discussionCategories(first: 25) { nodes { id name } }
            discussions(first: 100, orderBy: {field: CREATED_AT, direction: DESC}) {
              nodes { title url }
            }
          }
        }
        """,
        {"owner": TARGET_OWNER, "name": TARGET_REPOSITORY},
    )["repository"]
    categories = {category["name"]: category["id"] for category in data["discussionCategories"]["nodes"]}
    if CATEGORY_NAME not in categories:
        raise DiscussionError(f"Discussion category not found: {CATEGORY_NAME}")
    discussions = {discussion["title"]: discussion["url"] for discussion in data["discussions"]["nodes"]}
    return data["id"], categories[CATEGORY_NAME], discussions


def create_discussion(token: str, repository_id: str, category_id: str, title: str, body: str) -> str:
    data = graphql(
        token,
        """
        mutation CreateReviewDiscussion($repositoryId: ID!, $categoryId: ID!, $title: String!, $body: String!) {
          createDiscussion(input: {
            repositoryId: $repositoryId,
            categoryId: $categoryId,
            title: $title,
            body: $body
          }) {
            discussion { url }
          }
        }
        """,
        {
            "repositoryId": repository_id,
            "categoryId": category_id,
            "title": title,
            "body": body,
        },
    )
    return data["createDiscussion"]["discussion"]["url"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=pathlib.Path, default=DEFAULT_CONFIG)
    parser.add_argument("--output", type=pathlib.Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()

    source_token = os.environ.get("SOURCE_GH_TOKEN")
    discussion_token = os.environ.get("DISCUSSION_GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not source_token or not discussion_token:
        raise SystemExit("SOURCE_GH_TOKEN and DISCUSSION_GH_TOKEN (or GITHUB_TOKEN) are required")

    config = json.loads(args.config.read_text(encoding="utf-8"))
    repository_id, category_id, existing = repository_context(discussion_token)
    mapping: dict[str, dict[str, str]] = {}

    for work in config["works"]:
        if work.get("reviewStatus") != "ready":
            continue
        release = latest_release(work["repository"], source_token)
        tag = release["tag_name"]
        title = f"Review: {work['title']} — {tag}"
        url = existing.get(title)
        if not url:
            reader_url = f"https://digitize.brotatotes.com/read/?work={work['id']}"
            body = (
                f"## {work['title']} {tag}\n\n"
                f"This discussion is for feedback on **{tag}** of *{work['title']}* by {work['author']}.\n\n"
                f"[Read this edition]({reader_url})\n\n"
                "When reporting an issue, please include the document or volume, PDF page number, "
                "the text as shown, and your suggested correction. General review comments are also welcome.\n\n"
                "Feedback here remains attached to this exact version. A later release will receive a new discussion."
            )
            url = create_discussion(discussion_token, repository_id, category_id, title, body)
            existing[title] = url
            print(f"created {title}: {url}")
        else:
            print(f"reused {title}: {url}")
        mapping[work["id"]] = {"tag": tag, "url": url}

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(mapping, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(mapping)} release discussions to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
