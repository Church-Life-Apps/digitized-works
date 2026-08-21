const FRESHNESS_LIMIT_MS = 12 * 60 * 60 * 1000;

const grid = document.querySelector("#book-grid");
const search = document.querySelector("#search");
const emptyState = document.querySelector("#empty-state");
const siteStatus = document.querySelector("#site-status");
let catalog;

function formatEastern(iso, includeDate = true) {
  const options = {
    timeZone: "America/New_York",
    hour: "numeric",
    minute: "2-digit",
    timeZoneName: "short",
  };
  if (includeDate) {
    options.month = "long";
    options.day = "numeric";
    options.year = "numeric";
  }
  return new Intl.DateTimeFormat("en-US", options).format(new Date(iso));
}

function freshnessFor(work) {
  const checkedAt = new Date(work.freshness.checkedAt).getTime();
  if (!Number.isFinite(checkedAt) || Date.now() - checkedAt > FRESHNESS_LIMIT_MS) {
    return {
      state: "unknown",
      label: "Freshness unknown",
      detail: `Last successfully checked ${formatEastern(work.freshness.checkedAt)}. A newer version may exist.`,
    };
  }
  if (work.freshness.state === "delayed") {
    return {state: "delayed", label: "Update delayed", detail: work.freshness.message};
  }
  if (work.freshness.state === "processing") {
    return {state: "processing", label: "Update processing", detail: work.freshness.message};
  }
  return {
    state: "current",
    label: "Current",
    detail: `Matches the latest release as of ${formatEastern(work.freshness.checkedAt)}.`,
  };
}

function readerUrl(work, document) {
  const params = new URLSearchParams({work: work.id, document: document.id});
  return `read/?${params}`;
}

function reviewFor(work) {
  if (work.reviewStatus === "ready") {
    return {
      state: "ready",
      label: "Ready for review",
      action: "Review this work",
    };
  }
  return {
    state: "in-progress",
    label: "In progress",
    action: "Preview work in progress",
  };
}

function bookCard(work) {
  const firstDocument = work.documents[0];
  const freshness = freshnessFor(work);
  const review = reviewFor(work);
  const card = document.createElement("article");
  card.className = "book-card";
  card.dataset.search = `${work.title} ${work.author}`.toLowerCase();
  card.innerHTML = `
    <div class="book-topline">
      <p class="book-author"></p>
      <span class="review-chip ${review.state}"></span>
    </div>
    <h3></h3>
    <p class="book-description"></p>
    <dl class="book-meta">
      <div><dt>Edition</dt><dd></dd></div>
      <div><dt>Documents</dt><dd></dd></div>
    </dl>
    <div class="book-actions">
      <a class="read-button ${review.state}"><span class="action-label"></span><span aria-hidden="true">→</span></a>
      <div class="book-links">
        <a class="feedback-link" target="_blank" rel="noopener" hidden>Leave feedback</a>
        <a class="details-link" target="_blank" rel="noopener">Release details</a>
      </div>
    </div>`;
  card.querySelector(".book-author").textContent = work.author;
  card.querySelector(".review-chip").textContent = review.label;
  card.querySelector("h3").textContent = work.title;
  card.querySelector(".book-description").textContent = work.description;
  const values = card.querySelectorAll("dd");
  values[0].textContent = work.release.tag;
  values[1].textContent = work.documents.length === 1 ? "1 complete work" : `${work.documents.length} volumes`;
  card.querySelector(".read-button").href = readerUrl(work, firstDocument);
  card.querySelector(".action-label").textContent = review.action;
  card.querySelector(".details-link").href = work.release.url;
  if (work.reviewDiscussionUrl) {
    const feedbackLink = card.querySelector(".feedback-link");
    feedbackLink.href = work.reviewDiscussionUrl;
    feedbackLink.hidden = false;
  }
  return card;
}

function workGroup(title, description, works, state) {
  const section = document.createElement("section");
  section.className = `work-group ${state}`;
  section.innerHTML = `
    <div class="work-group-heading">
      <h3></h3>
      <p></p>
    </div>
    <div class="book-grid"></div>`;
  section.querySelector("h3").textContent = title;
  section.querySelector("p").textContent = description;
  const groupGrid = section.querySelector(".book-grid");
  works.forEach((work) => groupGrid.append(bookCard(work)));
  return section;
}

function unreleasedCard(work) {
  const card = document.createElement("article");
  card.className = "book-card unreleased";
  card.dataset.search = `${work.title} ${work.author}`.toLowerCase();
  card.innerHTML = `
    <div class="book-topline">
      <p class="book-author"></p>
      <span class="review-chip in-progress">In progress</span>
    </div>
    <h3></h3>
    <p class="book-description"></p>
    <dl class="book-meta">
      <div><dt>Release</dt><dd>Not available yet</dd></div>
      <div><dt>Preview</dt><dd>Not available yet</dd></div>
    </dl>`;
  card.querySelector(".book-author").textContent = work.author;
  card.querySelector("h3").textContent = work.title;
  card.querySelector(".book-description").textContent = work.description;
  return card;
}

function upcomingCard(work) {
  const card = document.createElement("article");
  card.className = "planned-card";
  card.innerHTML = `
    <div class="book-topline">
      <p class="book-author"></p>
      <span class="review-chip planned">Planned</span>
    </div>
    <h4></h4>
    <p class="book-description"></p>
    <p class="source-status ${work.sourceStatus === "Source research ongoing" ? "researching" : "found"}"></p>`;
  card.querySelector(".book-author").textContent = work.author;
  card.querySelector("h4").textContent = work.title;
  card.querySelector(".book-description").textContent = work.description;
  card.querySelector(".source-status").textContent = work.sourceStatus;
  return card;
}

function upcomingGroup(title, description, works, state) {
  const section = document.createElement("section");
  section.className = `work-group ${state}`;
  section.innerHTML = `
    <div class="work-group-heading">
      <h3></h3>
      <p></p>
    </div>
    <div class="planned-grid"></div>`;
  section.querySelector("h3").textContent = title;
  section.querySelector("p").textContent = description;
  const upcomingGrid = section.querySelector(".planned-grid");
  works.forEach((work) => upcomingGrid.append(upcomingCard(work)));
  return section;
}

function renderWorks(query = "") {
  const normalized = query.trim().toLowerCase();
  grid.replaceChildren();
  const matches = catalog.works.filter((work) => `${work.title} ${work.author}`.toLowerCase().includes(normalized));
  const upcomingMatches = (catalog.plannedWorks || []).filter((work) => `${work.title} ${work.author}`.toLowerCase().includes(normalized));
  const ready = matches.filter((work) => work.reviewStatus === "ready");
  const inProgress = matches.filter((work) => work.reviewStatus !== "ready");
  const unreleased = upcomingMatches.filter((work) => work.projectStatus === "in-progress");
  const planned = upcomingMatches.filter((work) => work.projectStatus !== "in-progress");
  if (ready.length) {
    grid.append(workGroup(
      "Ready for review",
      "These editions are stable enough for outside feedback.",
      ready,
      "ready",
    ));
  }
  if (inProgress.length || unreleased.length) {
    const section = workGroup(
      "In progress",
      "These editions are still being digitized or prepared for review.",
      inProgress,
      "in-progress",
    );
    const inProgressGrid = section.querySelector(".book-grid");
    unreleased.forEach((work) => inProgressGrid.append(unreleasedCard(work)));
    grid.append(section);
  }
  if (planned.length) {
    grid.append(upcomingGroup(
      "Planned works",
      "Source editions are being evaluated before digitization begins.",
      planned,
      "planned",
    ));
  }
  emptyState.hidden = matches.length !== 0 || upcomingMatches.length !== 0;
}

function renderStatus() {
  const unknown = catalog.works.some((work) => freshnessFor(work).state === "unknown");
  if (unknown) {
    siteStatus.className = "site-status warning";
    siteStatus.innerHTML = `<strong>Freshness check overdue.</strong> The library was last successfully checked ${formatEastern(catalog.generatedAt)}. A newer release may exist.`;
  } else {
    siteStatus.className = "site-status current";
    siteStatus.innerHTML = `<span class="status-dot" aria-hidden="true"></span><strong>All titles current.</strong> Latest releases verified ${formatEastern(catalog.generatedAt)}.`;
  }
}

async function loadCatalog() {
  try {
    const response = await fetch("catalog.json", {cache: "no-store"});
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    catalog = await response.json();
    renderStatus();
    renderWorks();
    search.addEventListener("input", () => renderWorks(search.value));
  } catch (error) {
    grid.innerHTML = `<div class="load-error"><strong>The library catalog could not be loaded.</strong><br>Please try again shortly.</div>`;
    siteStatus.textContent = "Library status unavailable.";
    siteStatus.className = "site-status warning";
    console.error(error);
  }
}

loadCatalog();
