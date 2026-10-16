import { defineConfig } from '@playwright/test';
import path from 'node:path';

export default defineConfig({
  testDir: './e2e',
  fullyParallel: false,
  workers: 1,
  timeout: 45000,
  use: {
    baseURL: 'http://127.0.0.1:8770',
    viewport: { width: 1440, height: 1000 },
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
    launchOptions: process.env.FOCO_BROWSER_PATH ? { executablePath: process.env.FOCO_BROWSER_PATH } : {},
  },
  webServer: {
    command: process.platform === 'win32' ? '.venv\\Scripts\\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8770 --no-access-log' : '.venv/bin/python -m uvicorn backend.main:app --host 127.0.0.1 --port 8770 --no-access-log',
    cwd: '..',
    url: 'http://127.0.0.1:8770/api/bootstrap',
    reuseExistingServer: false,
    env: { FOCO_DATA_DIR: path.resolve('../artifacts/e2e-data'), FOCO_PORT: '8770', FOCO_OLLAMA_URL: 'http://127.0.0.1:1' },
  },
});
