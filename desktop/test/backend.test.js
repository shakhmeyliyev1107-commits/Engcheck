"use strict";
const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");
const { startBackend, ping, isAppUrl } = require("../src/backend");

const BACKEND_DIR = path.join(__dirname, "..", "..", "backend");
const tmp = () => fs.mkdtempSync(path.join(os.tmpdir(), "engcheck-desktop-"));
const env = { ...process.env, ENGCHECK_ENCRYPT: "0" };

test("xizmat tasodifiy portda ishga tushadi, javob beradi va to'xtaydi", async () => {
  const dataDir = tmp();
  const b = await startBackend({ command: "python", args: ["-m", "engcheck"], cwd: BACKEND_DIR, dataDir, env });
  try {
    assert.ok(b.port > 1024 && b.port < 65536);
    assert.equal(await ping(b.port), true);
    assert.ok(fs.existsSync(path.join(dataDir, "engcheck.db")));
  } finally {
    await b.stop();
  }
  assert.equal(await ping(b.port, 500), false);
  assert.notEqual(b.process.exitCode ?? b.process.signalCode, null);
});

test("ikki nusxa bir vaqtda turli portlarda ishlaydi", async () => {
  const opts = () => ({ command: "python", args: ["-m", "engcheck"], cwd: BACKEND_DIR, dataDir: tmp(), env });
  const [a, b] = await Promise.all([startBackend(opts()), startBackend(opts())]);
  try {
    assert.notEqual(a.port, b.port);
  } finally {
    await Promise.all([a.stop(), b.stop()]);
  }
});

test("mavjud bo'lmagan buyruq tushunarli xato beradi", async () => {
  await assert.rejects(startBackend({ command: "bunday-buyruq-yoq-xyz", dataDir: tmp() }), /ishga tushirib bo'lmadi/);
});

test("darhol yopiladigan jarayon osilib qolmaydi", async () => {
  const started = Date.now();
  await assert.rejects(startBackend({ command: "python", args: ["-c", "import sys; sys.stderr.write('xato matni'); sys.exit(3)", "--"], dataDir: tmp() }),
    /kutilmaganda to'xtadi \(kod 3\)[\s\S]*xato matni/);
  assert.ok(Date.now() - started < 10_000);
});

test("javob bermaydigan jarayon taymaut bilan to'xtatiladi", async () => {
  const p = startBackend({ command: "python", args: ["-c", "import time; time.sleep(60)", "--"], dataDir: tmp(), timeoutMs: 1500 });
  await assert.rejects(p, /1.5 soniyada ishga tushmadi/);
});

test("shifrlangan baza kalitsiz bo'lsa sabab aytiladi", async () => {
  const dataDir = tmp();
  fs.writeFileSync(path.join(dataDir, "engcheck.db"), Buffer.alloc(4096, 7));   // SQLite sarlavhasi yo'q: shifrlangan deb olinadi
  await assert.rejects(startBackend({ command: "python", args: ["-m", "engcheck"], cwd: BACKEND_DIR, dataDir, env: process.env }),
    /Baza shifrlangan, lekin kaliti topilmadi/);
});

test("navigatsiya faqat o'z xizmatimizga ruxsat etiladi", () => {
  assert.equal(isAppUrl("http://127.0.0.1:5000/projects", 5000), true);
  for (const url of ["http://127.0.0.1:5001/", "https://127.0.0.1:5000/", "http://localhost:5000/", "http://127.0.0.1.evil.com:5000/",
                     "http://evil.com/", "file:///etc/passwd", "javascript:alert(1)", "not a url"]) {
    assert.equal(isAppUrl(url, 5000), false, url);
  }
});
