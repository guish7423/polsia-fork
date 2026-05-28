/** @type {import('next').NextConfig} */
const nextConfig = {
  output: process.env.NEXT_EXPORT ? "export" : "standalone",
  reactStrictMode: true,
  images: { unoptimized: true },
  env: {
    NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL || "http://localhost",
    NEXT_PUBLIC_WS_URL: process.env.NEXT_PUBLIC_WS_URL || "ws://localhost",
  },
};

module.exports = nextConfig;
