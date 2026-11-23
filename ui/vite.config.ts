import { fileURLToPath, URL } from "node:url";
import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { capabilityDesktops } from "./capability-desktops-plugin";

const repoRoot = fileURLToPath(new URL("..", import.meta.url));
const capabilityRoot = fileURLToPath(new URL("../capability", import.meta.url));
const reactPackage = fileURLToPath(new URL("./node_modules/react", import.meta.url));

export default defineConfig({
  base: "./",
  plugins: [capabilityDesktops(capabilityRoot), react(), tailwindcss()],
  resolve: {
    alias: [
      { find: "@", replacement: fileURLToPath(new URL("./src", import.meta.url)) },
      { find: /^react$/, replacement: reactPackage },
      {
        find: /^react\/jsx-runtime$/,
        replacement: fileURLToPath(new URL("./node_modules/react/jsx-runtime", import.meta.url)),
      },
      {
        find: /^react\/jsx-dev-runtime$/,
        replacement: fileURLToPath(new URL("./node_modules/react/jsx-dev-runtime", import.meta.url)),
      },
    ],
  },
  optimizeDeps: {
    exclude: ["virtual:capability-desktops"],
  },
  server: {
    fs: {
      allow: [repoRoot],
    },
  },
});
