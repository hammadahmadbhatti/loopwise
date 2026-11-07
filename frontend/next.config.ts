import path from "node:path";
import type { NextConfig } from "next";

// The dashboard talks to the FastAPI backend through same-origin /api/* requests.
// In development and in `next start`, Next proxies them to BACKEND_URL; in production
// a reverse proxy (Caddy/nginx) can route /api to the backend directly.
const backend = process.env.BACKEND_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  turbopack: {
    root: path.join(__dirname),
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${backend}/api/:path*` }];
  },
};

export default nextConfig;
