# Deployment

No hosting account, domain or Tavily credential is configured. Local PostgreSQL
17 integration and report persistence across restart have passed.
The container files are prepared but cannot be built or run here because Docker
is unavailable. Do not tag a production release until the gates below pass.

## Reproducible local container candidate

1. Install Docker with Compose. Copy `.env.example` to `.env`.
2. Set the database initialization variables and connection URLs. For example,
   using a new local development database only:

   ```dotenv
   POSTGRES_USER=claim_check
   POSTGRES_PASSWORD=local_dev_password
   POSTGRES_DB=claim_check
   DATABASE_URL=postgresql://claim_check:local_dev_password@localhost:5432/claim_check
   CONTAINER_DATABASE_URL=postgresql://claim_check:local_dev_password@db:5432/claim_check
   PROVIDER_MODE=fixture
   ```

3. From the repository root:

   ```sh
   docker compose -f compose.yaml -f compose.app.yaml up --build -d --wait
   docker compose -f compose.yaml -f compose.app.yaml logs api web
   curl --fail http://localhost:3000/api/v1/ready
   ```

   The API runs numbered migrations before serving requests. The frontend build
   and runtime both use `http://api:8000`. Database data and downloaded model files
   live in separate named volumes. The backend image includes local ML/OCR
   dependencies and may be large; first model use downloads weights.

4. Test the fixture flow and PostgreSQL report persistence, including restarting
   the containers and reopening a share link. Then set `PROVIDER_MODE=live` and
   `TAVILY_API_KEY` and recreate the API container. Test live queries and
   provider failures before making it public. There is no fallback from failed
   live research to fixtures.

## Account-dependent public deployment

The simplest target is a single Linux host running the same Compose stack, with
HTTPS terminated by a reverse proxy. This preserves Next.js, FastAPI and
PostgreSQL and avoids splitting synchronous ML requests across short-lived
serverless functions.

You must perform these account/infrastructure steps:

1. Obtain a host with Docker and sufficient RAM/disk for PyTorch, OCR and model
   weights. Start with a development host and measure its resource needs; no
   production capacity or cost has been measured here.
2. Configure a DNS name and trusted HTTPS certificate for that host. Configure
   its reverse proxy to send the web origin to `127.0.0.1:3000`, permit image
   bodies up to 5 MB plus HTTP overhead and permit investigation responses up to
   the two-minute browser request timeout. Do not expose the API or database
   ports publicly.
3. Copy the repository to the host; create `.env` there with unique database
   credentials. URL-encode credentials in URLs. Keep secrets out of source
   control, screenshots and build arguments. For external PostgreSQL, set the
   API database URL to the provider's TLS connection string and adjust Compose
   to remove the local database dependency.
4. Use the container commands above and run migrations/readiness checks. Enable
   live mode only after configuring the Tavily key. Verify a real investigation,
   report persistence, image correction, rate limiting and extension connection.
5. Set the extension's connection origin to your HTTPS web URL and approve access
   to that specific host. No provider keys go into the extension.

No deployment command has been executed against a hosting account. A Vercel
frontend is possible, but is not configured or verified here; its proxy timeout
must accommodate synchronous local ML on the separate backend.

## Release gates

- Both PostgreSQL integration tests passed on local PostgreSQL 17; rerun on the target database.
- Both container images build and the stack passes readiness and restart tests.
- Playwright/axe passes locally; confirm the configured Linux CI run.
- Native Chrome and Edge extension menu/sidebar/page flows are checked.
- Tavily live search, extraction, complete inference and failure behavior are checked.
- HTTPS, database backups, retention policy and abuse/resource limits are reviewed.

The current rate limiter is per API process and per direct peer IP. Behind the web
proxy, visitors share that peer budget. It deliberately ignores client-supplied
forwarded headers. Run one API worker for this prototype. It is not a distributed
limiter or a guarantee against sophisticated abuse. Add infrastructure-level
limits and explicit trusted-proxy handling only when deployment requires them.

## GitHub release (manual account access required)

Configure your own Git author identity, create a GitHub repository and add its
remote. Review the files and make logical commits; no identity was invented and
no remote, commit, push, tag or release was created here. The repository uses the MIT license.

After all release gates pass, from a clean committed `main` checkout:

```sh
git tag -a v1.0.0 -m "Claim Check v1.0.0"
git push origin main
git push origin v1.0.0
```

Create the GitHub release from that tag. Use `docs/github-release-checklist.md`
to confirm every release step, and cite the real numbers from
`docs/remediation-final-report.md` (or a later evaluation report) rather than
writing new release notes that restate unverified claims.

## Provider setup policy

The prepared frontend/backend target is a single Docker host; PostgreSQL runs in
Compose. Vercel or Supabase are optional alternatives, not configured deployments.
Production uses server-side `SEARCH_PROVIDER=tavily`, `TAVILY_API_KEY`,
`PROVIDER_MODE=live` and
`ALLOW_RUNTIME_PROVIDER_KEYS=false`. The full Compose file explicitly disables
runtime credentials. Configure unique database credentials and
`CONTAINER_DATABASE_URL`; the web build/runtime API origin is `http://api:8000`.
No public visitor should enter the operator's provider key.

Local runtime entry requires a trusted localhost installation outside this
container network. See final-configuration.md. Do not enable it behind public proxies
or tunnels. No remote BYOK/session isolation is implemented.

## Initialize the GitHub repository

Replace placeholders with the repository owner's identity and actual remote.
These commands are manual configuration, not evidence that publication occurred:

```sh
git config user.name "<author name>"
git config user.email "<author email>"
git remote add origin <repository-url>
git status --short
git add .
git commit -m "Prepare Claim Check portfolio release candidate"
git push -u origin main
```

Inspect the staged files before committing. Current work is uncommitted because
identity is absent; historical milestone boundaries cannot honestly be recreated
as completed commits. After CI and the integration gates pass, use the v1.0.0
commands above and update candidate release notes with actual results.
