import type { NextConfig } from "next";

const isStandalone =
  process.env.NEXT_OUTPUT_STANDALONE === "true" ||
  process.env.DOCKER_BUILD === "true" ||
  process.env.RENDER === "true";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  output: isStandalone ? "standalone" : undefined,
  images: {
    unoptimized: true,
  },
  eslint: {
    ignoreDuringBuilds: true,
  },
  typescript: {
    ignoreBuildErrors: false,
  },
};

export default nextConfig;
