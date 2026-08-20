import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Allow loading GitHub avatar images
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "avatars.githubusercontent.com",
      },
    ],
  },
  // Proxy /api/v1 → FastAPI backend during development
  async rewrites() {
    return [
      {
        source: "/api/v1/:path*",
        destination: `${process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1"}/:path*`,
      },
    ];
  },
};

export default nextConfig;
