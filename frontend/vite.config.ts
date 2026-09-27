import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    // Needed for the file watcher to see host edits from inside the container.
    watch: { usePolling: true },
  },
});
