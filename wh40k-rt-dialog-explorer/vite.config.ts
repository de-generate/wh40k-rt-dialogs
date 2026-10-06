/// <reference types="vitest/config" />
import { defineConfig } from "vite";
import solid from "@solidjs/vite-plugin";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [solid(), tailwindcss()],
  // Relative asset paths, so the build works from any directory of a static host.
  base: "./",
  // Tests cover plain TypeScript logic; they don't need a DOM.
  test: { environment: "node" },
});
