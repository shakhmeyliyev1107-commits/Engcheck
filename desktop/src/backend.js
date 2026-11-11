// Python xizmatini ishga tushirish va to'xtatish. Electron'ga bog'liq emas — alohida testlanadi.
"use strict";
const { spawn } = require("node:child_process");
const http = require("node:http");

const START_TIMEOUT_MS = 30_000;

/** Xizmat `/api/setup` ga javob berishini tekshiradi. */
function ping(port, timeoutMs = 2000) {
  return new Promise((resolve) => {
    const req = http.get({ host: "127.0.0.1", port, path: "/api/setup", timeout: timeoutMs }, (res) => {
      res.resume();
      resolve(res.statusCode === 200);
    });
    req.on("error", () => resolve(false));
    req.on("timeout", () => { req.destroy(); resolve(false); });
  });
}

/**
 * Xizmatni ishga tushiradi va tayyor bo'lguncha kutadi.
 * @param {{command: string, args?: string[], dataDir: string, cwd?: string, env?: object, timeoutMs?: number,
 *          onExit?: (code: number|null) => void}} options  onExit — xizmat ish paytida kutilmaganda to'xtasa chaqiriladi
 * @returns {Promise<{port: number, process: import("node:child_process").ChildProcess, stop: () => Promise<void>}>}
 */
function startBackend(options) {
  const { command, args = [], dataDir, cwd, env = process.env, timeoutMs = START_TIMEOUT_MS, onExit } = options;
  return new Promise((resolve, reject) => {
    let settled = false;
    let stderr = "";
    let buffer = "";
    // --port 0: xizmat bo'sh portni o'zi tanlaydi va stdout ga {"event":"ready","port":N} yozadi.
    const child = spawn(command, [...args, "--port", "0", "--data-dir", dataDir], {
      cwd,
      // stdin quvuri ochiq turadi: qobiq yopilsa yoki yiqilsa, quvur uziladi va xizmat o'zi to'xtaydi.
      env: { ...env, ENGCHECK_EXIT_WITH_PARENT: "1" },
      stdio: ["pipe", "pipe", "pipe"],
    });
    child.stdin.on("error", () => {});

    const fail = (error) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      if (child.exitCode === null) child.kill();
      reject(error);
    };
    const timer = setTimeout(() => fail(new Error(`Xizmat ${timeoutMs / 1000} soniyada ishga tushmadi.\n${stderr.slice(-2000)}`)), timeoutMs);

    child.on("error", (err) => fail(new Error(`Xizmatni ishga tushirib bo'lmadi: ${err.message}`)));
    child.on("exit", (code) => fail(new Error(`Xizmat kutilmaganda to'xtadi (kod ${code}).\n${stderr.slice(-2000)}`)));
    child.stderr.on("data", (d) => { stderr = (stderr + d).slice(-8000); });
    child.stdout.on("data", async (data) => {
      buffer += data;
      let nl;
      while ((nl = buffer.indexOf("\n")) >= 0) {
        const line = buffer.slice(0, nl).trim();
        buffer = buffer.slice(nl + 1);
        if (!line.startsWith("{")) continue;
        let event;
        try { event = JSON.parse(line); } catch { continue; }
        if (event.event === "error") {
          fail(new Error(event.code === "database_locked"
            ? "Baza shifrlangan, lekin kaliti topilmadi. Ma'lumotlar papkasi boshqa kompyuterdan ko'chirilgan bo'lishi mumkin."
            : `Xizmat xatosi: ${event.code}`));
          return;
        }
        if (event.event === "ready" && Number.isInteger(event.port) && !settled) {
          let alive = false;
          for (let i = 0; i < 10 && !alive && !settled; i++) {   // bir necha soniya ichida qayta urinish
            alive = await ping(event.port);
            if (!alive) await new Promise((r) => setTimeout(r, 300));
          }
          if (settled) return;
          if (!alive) { fail(new Error("Xizmat tayyor deb xabar berdi, lekin javob bermayapti.")); return; }
          settled = true;
          clearTimeout(timer);
          child.removeAllListeners("exit");
          let stopping = false;
          child.on("exit", (code) => { if (!stopping && onExit) onExit(code); });
          resolve({ port: event.port, process: child, stop: () => { stopping = true; return stopBackend(child); } });
        }
      }
    });
  });
}

/** Xizmatni to'xtatadi: avval muloyim, 5 soniyadan keyin majburan. */
function stopBackend(child) {
  return new Promise((resolve) => {
    if (child.exitCode !== null || child.signalCode !== null) return resolve();
    const force = setTimeout(() => child.kill("SIGKILL"), 5000);
    child.once("exit", () => { clearTimeout(force); resolve(); });
    child.kill();
  });
}

/** Oynadagi navigatsiyaga ruxsat: faqat o'z xizmatimiz manzili. */
function isAppUrl(url, port) {
  try {
    const u = new URL(url);
    return u.protocol === "http:" && u.hostname === "127.0.0.1" && u.port === String(port);
  } catch {
    return false;
  }
}

module.exports = { startBackend, stopBackend, ping, isAppUrl };
