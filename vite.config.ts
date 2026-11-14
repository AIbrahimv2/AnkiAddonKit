import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The kit's own window (py/page.py) inlines one IIFE bundle and one
// stylesheet, so build them with fixed names into py/web/, which sync.py
// copies into each add-on as src/kit/web/.
export default defineConfig({
  plugins: [react()],
  root: "standalone",
  base: "./",
  build: {
    outDir: "../py/web",
    emptyOutDir: true,
    cssCodeSplit: false,
    target: "chrome118",
    rollupOptions: {
      input: "standalone/main.tsx",
      output: {
        format: "iife",
        entryFileNames: "page.js",
        assetFileNames: "page[extname]",
      },
    },
  },
  // `npm run dev` serves standalone/index.html; bridge calls go to
  // tools/preview.py, which answers with the real kit code and the add-ons'
  // real changelogs.
  // The page's modules sit outside `root`, so name the dependencies up
  // front: found late, Vite would bundle React twice.
  optimizeDeps: { include: ["react", "react-dom/client", "react/jsx-runtime", "react/jsx-dev-runtime", "lucide-react"] },
  server: {
    port: 5184,
    proxy: { "/bridge": "http://127.0.0.1:5185" },
  },
});
