const FRESHNESS_LIMIT_MS = 12 * 60 * 60 * 1000;
const params = new URLSearchParams(window.location.search);

function formatEastern(iso) {
  return new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York",
    month: "long",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short",
  }).format(new Date(iso));
}

function freshnessFor(work) {
  const checkedAt = new Date(work.freshness.checkedAt).getTime();
  if (!Number.isFinite(checkedAt) || Date.now() - checkedAt > FRESHNESS_LIMIT_MS) {
    return {
      state: "unknown",
      title: "Freshness unknown",
      message: `You are reading ${work.release.tag}. The library has not successfully checked for updates since ${formatEastern(work.freshness.checkedAt)}. A newer version may exist.`,
    };
  }
  if (work.freshness.state === "delayed") {
    return {state: "delayed", title: "Update delayed", message: work.freshness.message};
  }
  if (work.freshness.state === "processing") {
    return {state: "processing", title: "Update processing", message: work.freshness.message};
  }
  return {
    state: "current",
    title: "Current",
    message: `Showing ${work.release.tag}. This matches the latest GitHub release, checked ${formatEastern(work.freshness.checkedAt)}.`,
  };
}

function renderReviewStatus(work) {
  const banner = document.querySelector("#review-banner");
  if (work.reviewStatus === "ready") {
    banner.className = "review-banner ready";
    banner.innerHTML = `<strong>In Review</strong><span>Feedback is welcome. Please include the document and PDF page with any comments.</span><a id="review-feedback-link" target="_blank" rel="noopener" hidden>Leave feedback on this version →</a>`;
    if (work.reviewDiscussionUrl) {
      const link = banner.querySelector("#review-feedback-link");
      link.href = work.reviewDiscussionUrl;
      link.hidden = false;
    }
  } else {
    banner.className = "review-banner in-progress";
    banner.innerHTML = `<strong>Work in progress</strong><span>This edition is available to preview, but review is not yet requested.</span>`;
  }
}

function setDocument(work, documentItem) {
  const pdfUrl = new URL(`../${documentItem.pdf}`, window.location.href).href;
  const viewerUrl = new URL("../vendor/pdfjs/web/viewer.html", window.location.href);
  viewerUrl.searchParams.set("file", pdfUrl);
  documentTitle = `${work.title} · ${documentItem.label}`;
  window.document.title = `${documentTitle} · Digitized Christian Works`;
  document.querySelector("#reader-title").textContent = `${work.title} · ${documentItem.label}`;
  document.querySelector("#pdf-frame").src = viewerUrl.href;
  document.querySelector("#open-pdf").href = pdfUrl;
  document.querySelector("#download-pdf").href = pdfUrl;

  const nextParams = new URLSearchParams({work: work.id, document: documentItem.id});
  history.replaceState(null, "", `?${nextParams}`);
  localStorage.setItem(`digitized-works:last-document:${work.id}`, documentItem.id);
}

let documentTitle;

async function initializeReader() {
  try {
    const response = await fetch("../catalog.json", {cache: "no-store"});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    const catalog = await response.json();
    const work = catalog.works.find((candidate) => candidate.id === params.get("work"));
    if (!work) throw new Error("Unknown work");

    const requestedDocument = params.get("document") || localStorage.getItem(`digitized-works:last-document:${work.id}`);
    const selected = work.documents.find((candidate) => candidate.id === requestedDocument) || work.documents[0];
    document.querySelector("#reader-author").textContent = work.author;
    document.querySelector("#release-version").textContent = `Showing ${work.release.tag}`;
    document.querySelector("#release-link").href = work.release.url;
    document.querySelector("#repository-link").href = `https://github.com/${work.repository}`;
    renderReviewStatus(work);

    const selector = document.querySelector("#document-select");
    work.documents.forEach((item) => {
      const option = document.createElement("option");
      option.value = item.id;
      option.textContent = item.label;
      option.selected = item.id === selected.id;
      selector.append(option);
    });
    selector.disabled = work.documents.length === 1;
    selector.addEventListener("change", () => {
      const next = work.documents.find((item) => item.id === selector.value);
      setDocument(work, next);
    });

    const freshness = freshnessFor(work);
    const banner = document.querySelector("#freshness-banner");
    banner.className = `freshness-banner ${freshness.state}`;
    banner.innerHTML = `<strong>${freshness.title}</strong><span>${freshness.message}</span>`;
    setDocument(work, selected);
  } catch (error) {
    document.querySelector("#reader-title").textContent = "Document unavailable";
    document.querySelector("#reader-error").hidden = false;
    document.querySelector("#pdf-frame").hidden = true;
    console.error(error);
  }
}

initializeReader();
