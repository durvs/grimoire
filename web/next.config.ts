import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Sem isto o Turbopack infere a raiz pelo lockfile mais acima no filesystem
  // (~/Workspace/pnpm-lock.yaml na máquina local), não por este projeto.
  turbopack: {
    root: __dirname,
  },
};

export default nextConfig;
