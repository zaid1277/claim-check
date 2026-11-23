# Claim Check browser extension

Plain JavaScript, Manifest V3. No build dependency or model logic is included.

Run the web/API services. Open chrome://extensions or edge://extensions, enable
Developer mode, choose Load unpacked and select this directory. Highlight a claim
on a regular page, right-click “Check with Claim Check”, review the side-panel
text and submit. “Open full investigation” opens the web result; “Check this page”
opens the URL input flow. Restricted browser pages cannot be investigated.

The default web origin is http://localhost:3000. Connection settings can request
access to your chosen HTTPS deployment origin. No search/model keys belong here.

`node --test extension/tests/*.test.mjs` from the repository root checks manifest
files, script syntax and background context handling. Native installation and
Chrome/Edge menu/sidebar gestures still need manual verification.

## Manual Chrome and Edge checklist

Repeat in each browser; native browser verification is not implied by unit tests.

1. Start the API and web app; configure search on the server or through localhost
   setup. For a deterministic smoke check, keep fixture mode enabled.
2. Open the browser extensions page, enable Developer mode and load this directory.
3. On a regular HTTP(S) page, select “The demonstration library opens on Sundays.”
   and choose **Check with Claim Check** from the context menu.
4. Confirm the side panel shows the selected text and page title. Edit the claim,
   submit, and inspect the assessment and fixture notice (in fixture mode).
5. Open the full investigation, publish a link and reopen its read-only report.
6. Use **Check this page**; confirm the web app receives the active page URL and
   requires claim review. Browser-internal pages should show an explanatory error.
7. Stop the API and submit again: confirm a useful connection error and re-enabled
   controls. Requests time out after two minutes rather than remaining busy forever.
8. In connection settings, test a deployed HTTPS origin and approve only its host.
   Confirm no provider credential is requested or stored by the extension.
