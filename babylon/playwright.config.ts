import { defineConfig, devices } from "@playwright/test";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const babylonRoot = dirname(fileURLToPath(import.meta.url));
const workspaceRoot = resolve(babylonRoot, "..");

export default defineConfig({
  testDir: "./tests",
  fullyParallel: false,
  workers: 1,
  timeout: 90_000,
  expect: { timeout: 10_000 },
  reporter: "list",
  use: {
    baseURL: "http://127.0.0.1:4173",
    ...devices["Desktop Chrome"],
    launchOptions: {
      args: ["--use-angle=swiftshader", "--enable-webgl", "--ignore-gpu-blocklist"],
    },
  },
  webServer: [
    {
      command: "npm run preview -- --host 127.0.0.1 --port 4173 --strictPort",
      cwd: babylonRoot,
      url: "http://127.0.0.1:4173",
      reuseExistingServer: !process.env.CI,
    },
    {
      command: `"${join(workspaceRoot, ".venv", "Scripts", "python.exe")}" -m streamlit run streamlit_app.py --server.headless true --server.address 127.0.0.1 --server.port 8503`,
      cwd: workspaceRoot,
      url: "http://127.0.0.1:8503/_stcore/health",
      reuseExistingServer: !process.env.CI,
    },
  ],
});