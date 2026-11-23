import type { NextConfig } from "next";

const config: NextConfig = {
  output: "standalone",
  // Live investigations can exceed Next's 30s default; match the client's budget.
  experimental: { proxyTimeout: 120_000 },
  async rewrites() {
    // Keep browser requests on one origin; the Python API owns investigation logic.
    return [
      {
        source: "/api/v1/:path*",
        destination: `${process.env.API_BASE_URL || "http://127.0.0.1:8000"}/api/v1/:path*`,
      },
    ];
  },
};
export default config;
