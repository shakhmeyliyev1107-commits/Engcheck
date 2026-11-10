import { defineConfig } from "@playwright/test";

const PORT = 8799;
const TMP = "e2e/.tmp";

// Har ishga tushirishda toza ma'lumotlar papkasi va yangi namunaviy hujjatlar.
export default defineConfig({
  testDir: "e2e",
  workers: 1,
  fullyParallel: false,
  timeout: 60_000,
  reporter: [["list"]],
  use: { baseURL: `http://127.0.0.1:${PORT}`, locale: "uz-UZ" },
  webServer: {
    command:
      `bash -c "rm -rf ${TMP} && mkdir -p ${TMP} && npm run build --silent && ` +
      `python ../samples/generate_sample_project.py ${TMP}/sample > /dev/null && ` +
      `cd ../backend && ENGCHECK_DATA_DIR=../frontend/${TMP}/data ENGCHECK_PORT=${PORT} python -m engcheck"`,
    url: `http://127.0.0.1:${PORT}/api/setup`,
    reuseExistingServer: false,
    timeout: 120_000,
  },
});
