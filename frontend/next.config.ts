import type { NextConfig } from "next";

const INTERNAL_API = process.env.INTERNAL_API_URL ?? "http://api:8000";

const nextConfig: NextConfig = {
  output: "standalone",
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${INTERNAL_API}/api/v1/:path*`,
      },
    ];
  },
};

export default nextConfig;
