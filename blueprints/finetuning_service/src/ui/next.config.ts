import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  output: 'standalone',
  basePath: process.env.NEXT_PUBLIC_BASE_PATH || '',
  /* config options here */
};
console.log("Next.js configuration:", nextConfig);

export default nextConfig;
