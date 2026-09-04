import { defineConfig, devices } from "@playwright/test";

const isCI = Boolean(process.env.CI);

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: isCI,
  retries: isCI ? 2 : 0,
  // One worker: Next.js compiles routes on demand in `next dev`, and parallel
  // first-visits race the default 5s URL assertion. The smoke suite is small.
  workers: 1,
  timeout: 60_000,
  expect: { timeout: 15_000 },
  reporter: isCI
    ? [
        ["github"],
        ["html", { open: "never", outputFolder: "playwright-report" }],
      ]
    : [["html", { open: "on-failure" }]],
  use: {
    baseURL: "http://127.0.0.1:3000",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  webServer: {
    // CI serves the production build (built in the workflow before this command).
    // Local runs use `next dev` so engineers are not forced through a full build.
    command: isCI ? "npm run start" : "npm run dev",
    url: "http://127.0.0.1:3000/login",
    reuseExistingServer: !isCI,
    timeout: 120_000,
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"] } }],
});
