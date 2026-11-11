// EngCheck desktop qobig'i: xizmatni ishga tushiradi va interfeysni oynada ochadi.
"use strict";
const { app, BrowserWindow, dialog, shell } = require("electron");
const path = require("node:path");
const { startBackend, isAppUrl } = require("./backend");

let backend = null;

/** Yig'ilgan ilovada — birga kelgan `engcheck-server`; ishlab chiqishda — `python -m engcheck`. */
function backendCommand() {
  if (app.isPackaged) {
    const exe = process.platform === "win32" ? "engcheck-server.exe" : "engcheck-server";
    return { command: path.join(process.resourcesPath, "engcheck-server", exe), args: [],
             env: { ...process.env, ENGCHECK_FRONTEND_DIST: path.join(process.resourcesPath, "frontend") } };
  }
  return { command: process.env.ENGCHECK_PYTHON || "python", args: ["-m", "engcheck"], cwd: path.join(__dirname, "..", "..", "backend") };
}

async function createWindow() {
  try {
    backend = await startBackend({ ...backendCommand(), dataDir: path.join(app.getPath("userData"), "data") });
  } catch (error) {
    dialog.showErrorBox("EngCheck ishga tushmadi", String(error.message || error));
    app.quit();
    return;
  }
  const win = new BrowserWindow({
    width: 1360, height: 880, minWidth: 900, minHeight: 600, title: "EngCheck",
    webPreferences: { contextIsolation: true, nodeIntegration: false, sandbox: true },
  });
  win.removeMenu();
  const port = backend.port;
  // Tashqi havolalar tizim brauzerida ochiladi; oyna faqat o'z xizmatimizni ko'rsatadi.
  win.webContents.setWindowOpenHandler(({ url }) => {
    if (/^https?:\/\//.test(url) && !isAppUrl(url, port)) shell.openExternal(url);
    return { action: "deny" };
  });
  win.webContents.on("will-navigate", (event, url) => {
    if (!isAppUrl(url, port)) event.preventDefault();
  });
  if (process.env.ENGCHECK_SMOKE) {   // tutun testi: sahifa yuklangach sarlavhani chiqarib, yopiladi
    win.webContents.once("did-finish-load", () => {
      console.log(JSON.stringify({ smoke: "loaded", title: win.webContents.getTitle(), url: win.webContents.getURL() }));
      app.quit();
    });
  }
  await win.loadURL(`http://127.0.0.1:${port}/`);
}

app.on("web-contents-created", (_e, contents) => {
  contents.on("will-attach-webview", (event) => event.preventDefault());
});
if (!app.requestSingleInstanceLock()) app.quit();
else app.whenReady().then(createWindow);

app.on("window-all-closed", () => app.quit());
app.on("before-quit", (event) => {
  if (!backend) return;
  event.preventDefault();          // xizmat to'xtaguncha kutamiz: yetim jarayon qolmasin
  const b = backend;
  backend = null;
  b.stop().finally(() => app.quit());
});
