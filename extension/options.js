const input = document.querySelector("#origin");
chrome.storage.local.get("webOrigin").then((data) => {
  input.value = data.webOrigin || "http://localhost:3000";
});
document
  .querySelector("#settings")
  .addEventListener("submit", async (event) => {
    event.preventDefault();
    const status = document.querySelector("#status");
    try {
      const url = new URL(input.value);
      if (
        url.username ||
        url.password ||
        (url.protocol !== "https:" &&
          !["http://localhost:3000", "http://127.0.0.1:3000"].includes(
            url.origin,
          ))
      )
        throw new Error("Use HTTPS or the local development origin.");
      if (
        url.protocol === "https:" &&
        !(await chrome.permissions.request({ origins: [`${url.origin}/*`] }))
      )
        throw new Error("Host access was not granted.");
      await chrome.storage.local.set({ webOrigin: url.origin });
      status.textContent = "Connection saved.";
    } catch (error) {
      status.textContent = error.message;
    }
  });
