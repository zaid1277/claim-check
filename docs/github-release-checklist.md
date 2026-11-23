# GitHub release checklist

Target: public `zaid1277/claim-check`. Release type: portfolio preview.
See [release verification](release-verification.md) for exact fresh results and
[deployment](deployment.md) for additional production-hosting gates.

## Locally completed

- [x] Backend suite with real-model and PostgreSQL integration: 171 passed.
- [x] Frontend, extension, Chromium/WebKit flows, types, lint, formatting and build.
- [x] One fresh live Tavily investigation, supporting passage and saved report.
- [x] Ignored environment files, caches, model weights and disposable databases.
- [x] Scanned publishable files for common credential/private-key patterns and
      source archives for environment/private-key filenames; no matches found.
- [x] README clone URL, recorded evaluation limitations, screenshots and demo.
- [x] CI configured to exercise the isolated Chromium/WebKit release suite.

## GitHub and deployment checks

- [ ] Push to the intended public repository and inspect rendered README/assets.
- [ ] Verify GitHub Actions on the uploaded commit; local success is not hosted CI success.
- [ ] Publish a portfolio pre-release with accurate limitations, not a production release.
- [ ] Validate the installed Chrome/Edge extension manually.
- [ ] Verify container deployment and persistence on the actual host before deployment.

On subsequent releases, re-scan all staged changes and history for secrets. Keep
recorded benchmark generations intact, and do not replace held-out results with
repeatedly tuned development scores.
