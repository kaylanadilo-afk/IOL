import type { NextConfig } from "next";

// URL del backend FastAPI. El front llama a /api/... y Next lo reenvía (sin problemas de CORS).
const API_URL = process.env.API_URL ?? "http://localhost:8000";

const nextConfig: NextConfig = {
  // Sin el botón "N" de Next en desarrollo (los errores se siguen mostrando)
  devIndicators: false,
  async rewrites() {
    return [{ source: "/api/:path*", destination: `${API_URL}/api/:path*` }];
  },
};

export default nextConfig;
