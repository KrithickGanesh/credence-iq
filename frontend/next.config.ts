import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: "standalone",
  reactStrictMode: true,
  eslint: {
    ignoreDuringBuilds: true,
  },
  // Keep the dev-only Next.js badge out of demo screenshots and screen recordings.
  devIndicators: false,
};

export default nextConfig;
