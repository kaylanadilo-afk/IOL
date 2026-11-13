import type { NextConfig } from "next";

// URL del backend FastAPI. El front llama a /api/... y Next lo reenvía (sin problemas de CORS).
const API_URL = process.env.API_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/api/:path*` }];
  },
};

export default nextConfig;
