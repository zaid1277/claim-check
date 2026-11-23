let selection = {};
const claim = document.querySelector("#claim");
const status = document.querySelector("#status");
const error = document.querySelector("#error");
const result = document.querySelector("#result");
const full = document.querySelector("#full");
function update(value) {
  selection = value || {};
  claim.value = selection.claim || "";
  document.querySelector("#context").textContent =
    selection.page_title || "No selected page context.";
  result.replaceChildren();
  full.hidden = true;
}
chrome.storage.session.get("selection").then((data) => update(data.selection));
chrome.storage.onChanged.addListener((changes, area) => {
  if (area === "session" && changes.selection)
    update(changes.selection.newValue);
});
async function origin() {
  return (
    (await chrome.storage.local.get("webOrigin")).webOrigin ||
    "http://localhost:3000"
  );
}
document.querySelector("#check").addEventListener("click", async () => {
  error.textContent = "";
  result.replaceChildren();
  full.hidden = true;
  if (claim.value.trim().length < 3) {
    error.textContent = "Enter a factual claim first.";
    return;
  }
  const button = document.querySelector("#check");
  button.disabled = true;
  status.textContent = "Checking evidence…";
  try {
    const base = await origin();
    // The extension sends page context; all investigation logic stays in the API.
    const response = await fetch(`${base}/api/v1/extension/check`, {
      method: "POST",
      signal: AbortSignal.timeout(120000),
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        ...selection,
        source_url: selection.source_url || null,
        claim: claim.value,
      }),
    });
    const data = await response.json();
    if (!response.ok)
      throw new Error(data.error?.message || "Investigation failed.");
    const heading = document.createElement("h2");
    heading.textContent = data.assessments[0].verdict.replaceAll("_", " ");
    result.append(heading);
    if (data.mode === "fixture") {
      const notice = document.createElement("p");
      notice.textContent = "Demonstration fixtures — not live research.";
      result.append(notice);
    }
    for (const assessment of data.assessments) {
      const explanation = document.createElement("p");
      explanation.textContent = assessment.explanation;
      result.append(explanation);
      for (const evidence of assessment.evidence) {
        const p = document.createElement("p");
        p.textContent = `${evidence.stance}: ${evidence.title} · ${evidence.published_at || "Date unavailable"} — ${evidence.passage}`;
        result.append(p);
      }
    }
    full.href = `${base}/investigations/${data.id}`;
    full.hidden = false;
    status.textContent = "Investigation complete.";
  } catch (e) {
    error.textContent = e.message || "Check connection settings and try again.";
    status.textContent = "";
  } finally {
    button.disabled = false;
  }
});
document.querySelector("#page").addEventListener("click", async () => {
  error.textContent = "";
  try {
    const [tab] = await chrome.tabs.query({
      active: true,
      currentWindow: true,
    });
    if (!tab?.url || !/^https?:\/\//.test(tab.url))
      throw new Error("Open a public article page first.");
    await chrome.tabs.create({
      url: `${await origin()}/?url=${encodeURIComponent(tab.url)}`,
    });
  } catch (e) {
    error.textContent = e.message;
  }
});
