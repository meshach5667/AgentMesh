import type { NextConfig } from "next";
import { API_URL } from "./src/lib/config";
import { securityHeaders } from "./src/lib/securityHeaders";

const nextConfig: NextConfig = {
  output: "standalone",
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders(API_URL, process.env.NODE_ENV !== "production") }];
  },
};

export default nextConfig;
