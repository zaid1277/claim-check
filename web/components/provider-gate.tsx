"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import Workbench from "./workbench";
import { request } from "../lib/api";

type Status = {
  ready: boolean;
  mode: string;
  runtime_keys_allowed: boolean;
  database_configured: boolean;
  providers: {
    search: { configured: boolean; provider: "tavily" | "brave" | "mock" };
  };
};

export default function ProviderGate({
  initialUrl = "",
}: {
  initialUrl?: string;
}) {
  const [status, setStatus] = useState<Status | null>(null);
  const [provider, setProvider] = useState<"tavily" | "brave">("tavily");
  const providerName = provider === "tavily" ? "Tavily" : "Brave";
  const [key, setKey] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const refresh = useCallback(async () => {
    try {
      const response = await fetch("/api/v1/setup/status", {
        cache: "no-store",
        signal: AbortSignal.timeout(10000),
      });
      if (!response.ok) throw new Error();
      setStatus(await response.json());
      setError("");
    } catch {
      setStatus(null);
      setError(
        "Claim Check cannot reach its server. Check that the API is running, then retry.",
      );
    }
  }, []);
  useEffect(() => {
    fetch("/api/v1/setup/status", {
      cache: "no-store",
      signal: AbortSignal.timeout(10000),
    })
      .then((response) => {
        if (!response.ok) throw new Error();
        return response.json();
      })
      .then(setStatus)
      .catch(() =>
        setError(
          "Claim Check cannot reach its server. Check that the API is running, then retry.",
        ),
      );
  }, []);

  if (status?.ready)
    return <Workbench initialUrl={initialUrl} onConfigurationError={refresh} />;

  async function connect(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      setStatus(
        await request<Status>("setup/providers", { provider, api_key: key }),
      );
    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Web search could not be connected.",
      );
    } finally {
      setKey("");
      setBusy(false);
    }
  }
  return (
    <div className="shell">
      <header className="masthead">
        <Link href="/">Claim Check</Link>
        <span>Research · Evidence · Context</span>
      </header>
      <main id="main">
        <p className="eyebrow">Claim Check setup</p>
        <h1>Connect research services</h1>
        {!status && !error && (
          <p role="status">Checking service configuration…</p>
        )}
        {status && (
          <>
            <p className="intro">
              Web search retrieves current evidence. Embeddings and evidence
              classification run locally without additional API keys.
            </p>
            <section className="assessment" aria-labelledby="search-heading">
              <h2 id="search-heading">
                {status.providers.search.configured
                  ? status.providers.search.provider === "brave"
                    ? "Brave Search"
                    : "Tavily Search"
                  : `${providerName} Search`}
              </h2>
              <p>Used to retrieve current evidence from the web.</p>
              <p>
                {status.providers.search.configured
                  ? "API key configured"
                  : "API key required"}
              </p>
              {!status.database_configured && (
                <p className="notice">
                  The report database still needs server configuration. Set
                  DATABASE_URL and apply migrations before live investigations.
                </p>
              )}
              {!status.providers.search.configured &&
                (status.runtime_keys_allowed ? (
                  <form onSubmit={connect} aria-busy={busy}>
                    <fieldset disabled={busy} className="input-modes">
                      <legend>Search provider</legend>
                      {(["tavily", "brave"] as const).map((value) => (
                        <label key={value}>
                          <input
                            type="radio"
                            name="provider"
                            checked={provider === value}
                            onChange={() => {
                              setProvider(value);
                              setKey("");
                              setError("");
                            }}
                          />{" "}
                          {value === "tavily" ? "Tavily" : "Brave"}
                        </label>
                      ))}
                    </fieldset>
                    <label htmlFor="provider-key">{providerName} API key</label>
                    <input
                      id="provider-key"
                      type="password"
                      autoComplete="off"
                      required
                      maxLength={512}
                      value={key}
                      onChange={(event) => setKey(event.target.value)}
                      aria-describedby="key-help"
                      disabled={busy}
                    />
                    <p id="key-help" className="muted">
                      For this local server only. The key stays in backend
                      memory and disappears on restart. Validation makes one
                      search request against the provider quota.
                    </p>
                    <p>
                      <a
                        href={
                          provider === "tavily"
                            ? "https://app.tavily.com/"
                            : "https://api-dashboard.search.brave.com/app/keys"
                        }
                        target="_blank"
                        rel="noreferrer"
                      >
                        Get a {providerName} API key
                      </a>
                    </p>
                    <button disabled={busy}>
                      {busy
                        ? "Validating web search…"
                        : "Validate and continue"}
                    </button>
                  </form>
                ) : (
                  <p className="notice">
                    Web search is not configured. The site operator must
                    configure the provider on the server; visitors do not need
                    to supply credentials.
                  </p>
                ))}
            </section>
            <p className="muted">
              Credentials are excluded from reports and are never written to
              repository files.
            </p>
          </>
        )}
        {error && (
          <p role="alert" className="notice">
            {error}
          </p>
        )}
        {busy && (
          <p role="status">Validating credentials with {providerName}.</p>
        )}
        <div className="actions">
          <button
            type="button"
            className="secondary"
            disabled={busy}
            onClick={() => void refresh()}
          >
            Retry connection
          </button>
        </div>
      </main>
      <footer>
        <Link href="/methodology">Methodology and limitations</Link>
      </footer>
    </div>
  );
}
