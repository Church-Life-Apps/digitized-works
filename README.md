# Digitized Christian Works

A static reading library for the latest verified editions produced by the Church-Life-Apps digitization projects.

## What it does

- Presents every available work in a clear, searchable library.
- Shows researched future titles separately as planned works.
- Creates a public, version-specific GitHub Discussion for each review-ready release.
- Opens PDFs in a bundled PDF.js reader with search, thumbnails, zoom, and navigation.
- Imports only the latest published, non-prerelease GitHub release.
- Validates every expected PDF before an atomic GitHub Pages deployment.
- Shows when each displayed release was last verified.
- Changes the status to **Freshness unknown** in the browser if no successful deployment has occurred within 12 hours.

## Local build

Requirements are Python 3.11 or later and Poppler's `pdfinfo` command.

```bash
python3 scripts/build.py
python3 scripts/verify_site.py dist
python3 -m http.server 8000 --directory dist
```

Then open <http://localhost:8000/>.

## Adding a work

Add its metadata and exact release PDF filenames to `catalog/sources.json`. The next build will fetch and validate the latest stable release. A missing, malformed, or unreadable asset fails the build and leaves the currently deployed site untouched.

## Deployment and freshness

The workflow runs after changes, on manual request, when sent a `digitization-release` repository dispatch, and every six hours as reconciliation. Deployments are atomic. A failed build cannot replace the last known-good site.

The public address is `https://digitize.brotatotes.com`.

## Content

The repository's code is separate from the digitized texts. Source and release history for each text remain in its linked Church-Life-Apps repository.
