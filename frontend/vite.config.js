import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";


export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@app": fileURLToPath(new URL("./src/app", import.meta.url)),
      "@domain": fileURLToPath(new URL("./src/domain", import.meta.url)),
      "@application": fileURLToPath(new URL("./src/application", import.meta.url)),
      "@infrastructure": fileURLToPath(new URL("./src/infrastructure", import.meta.url)),
      "@presentation": fileURLToPath(new URL("./src/presentation", import.meta.url)),
      "@shared": fileURLToPath(new URL("./src/shared", import.meta.url)),
    },
  },
  server: {
    host: "127.0.0.1",
    port: 5173,
  },
});
