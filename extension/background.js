chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "claim-check",
    title: "Check with Claim Check",
    contexts: ["selection"],
  });
  chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true });
});
chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (info.menuItemId !== "claim-check" || !tab?.id) return;
  // Opening must remain in the user gesture; the panel listens for stored context.
  chrome.sidePanel.open({ tabId: tab.id });
  chrome.storage.session.set({
    selection: {
      claim: info.selectionText || "",
      source_url: info.pageUrl || "",
      page_title: tab.title || "",
    },
  });
});
