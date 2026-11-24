const { app, BrowserWindow, ipcMain, screen } = require("electron");
const fs = require("node:fs");
const path = require("node:path");
const { KernelSession } = require("./kernel-session.cjs");
const { SecureEnvironmentFile } = require("./secure-environment.cjs");

const devUrl = process.env.VITE_DEV_SERVER_URL;
const repoRoot = path.resolve(__dirname, "../..");
const PRESENT_TIMEOUT_MS = 1500;

function cursorWorkArea() {
  return screen.getDisplayNearestPoint(screen.getCursorScreenPoint()).workArea;
}

let mainWindow = null;
let kernelSession = null;
const secureEnvironment = new SecureEnvironmentFile();
const semanticActions = new Set([
  "chat.send",
  "process.send",
  "process.create",
  "environment.load",
  "model.catalog",
  "model.configure",
  "memory.configure",
  "capability.call",
]);

function createWindow() {
  const area = cursorWorkArea();
  const win = new BrowserWindow({
    x: area.x,
    y: area.y,
    width: area.width,
    height: area.height,
    backgroundColor: "#000000",
    autoHideMenuBar: true,
    show: false,
    webPreferences: {
      contextIsolation: true,
      nodeIntegration: false,
      backgroundThrottling: false,
      preload: path.join(__dirname, "preload.cjs"),
    },
  });
  win.setBounds(area);
  mainWindow = win;
  kernelSession = new KernelSession({
    cwd: repoRoot,
    onEvent(event) {
      if (!win.isDestroyed()) {
        win.webContents.send("kernel:event", event);
      }
    },
  });

  let shown = false;
  const showWindow = () => {
    if (shown || win.isDestroyed()) {
      return;
    }
    shown = true;
    clearTimeout(presentTimer);
    ipcMain.removeListener("ui:presented", onPresented);
    win.show();
  };
  const onPresented = (event) => {
    if (event.sender !== win.webContents) {
      return;
    }
    showWindow();
  };
  const presentTimer = setTimeout(showWindow, PRESENT_TIMEOUT_MS);
  ipcMain.on("ui:presented", onPresented);

  win.on("closed", () => {
    clearTimeout(presentTimer);
    ipcMain.removeListener("ui:presented", onPresented);
    kernelSession?.stop();
    secureEnvironment.cleanup();
    kernelSession = null;
    mainWindow = null;
  });

  if (devUrl) {
    win.loadURL(devUrl);
    return;
  }

  win.loadFile(path.join(__dirname, "../dist/index.html"));
}

ipcMain.on("connection:action", (event, request) => {
  if (
    event.sender !== mainWindow?.webContents ||
    !request ||
    typeof request !== "object" ||
    !semanticActions.has(request.action) ||
    !request.payload ||
    typeof request.payload !== "object" ||
    typeof request.request_id !== "string" ||
    !request.request_id
  ) {
    return;
  }
  kernelSession?.request(request.action, request.payload, request.request_id);
});

ipcMain.on("connection:secret", (event, request) => {
  if (
    event.sender !== mainWindow?.webContents ||
    !request ||
    typeof request !== "object" ||
    typeof request.request_id !== "string" ||
    !request.request_id ||
    typeof request.key !== "string" ||
    !request.key ||
    typeof request.value !== "string" ||
    request.key.includes("=") ||
    /[\s\0]/.test(request.key) ||
    /[\r\n\0]/.test(request.value)
  ) {
    return;
  }
  try {
    const secretFile = secureEnvironment.write(request.key, request.value);
    kernelSession?.request(
      "environment.load",
      { keys: [request.key], path: secretFile },
      request.request_id,
    );
  } catch (error) {
    if (!mainWindow?.isDestroyed()) {
      mainWindow?.webContents.send("kernel:event", {
        data: {
          action: "environment.secret",
          error: {
            code: "secret_write_failed",
            message: error instanceof Error ? error.message : String(error),
          },
        },
        kind: "action.failed",
        request_id: request.request_id,
        seq: Number.MAX_SAFE_INTEGER,
        version: 1,
      });
    }
  }
});

ipcMain.on("connection:stop", (event) => {
  if (event.sender === mainWindow?.webContents) {
    kernelSession?.stop();
  }
});

const promptCapabilities = new Set(["agent_loop", "agent_loop_pi"]);

function promptFile(capability) {
  if (!promptCapabilities.has(capability)) {
    throw new Error("unknown prompt");
  }
  return path.join(repoRoot, ".linope", "prompts", `${capability}.md`);
}

function assertPromptWindow(event) {
  if (event.sender !== mainWindow?.webContents) {
    throw new Error("unknown window");
  }
}

ipcMain.handle("prompt:stage", (event, request) => {
  assertPromptWindow(event);
  if (!request || typeof request.capability !== "string") {
    throw new Error("prompt needs a capability");
  }
  const file = promptFile(request.capability);
  if (request.text === null) {
    fs.rmSync(file, { force: true });
    return { path: "" };
  }
  if (typeof request.text !== "string") {
    throw new Error("prompt needs text");
  }
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, request.text, "utf8");
  return { path: file };
});

app.whenReady().then(createWindow);

app.on("before-quit", () => {
  kernelSession?.stop();
  secureEnvironment.cleanup();
});

app.on("window-all-closed", () => {
  if (process.platform !== "darwin") {
    app.quit();
  }
});
