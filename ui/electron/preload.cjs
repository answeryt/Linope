const { contextBridge, ipcRenderer } = require("electron");

let actionSequence = 0;

function sendAction(action, payload) {
  const requestId = `renderer-${++actionSequence}`;
  ipcRenderer.send("connection:action", {
    action,
    payload,
    request_id: requestId,
  });
  return requestId;
}

function saveSecret(input) {
  const requestId = `renderer-${++actionSequence}`;
  ipcRenderer.send("connection:secret", {
    key: input.key,
    request_id: requestId,
    value: input.value,
  });
  return requestId;
}

contextBridge.exposeInMainWorld("linopeKernel", {
  chat: {
    send(text) {
      return sendAction("chat.send", { text });
    },
  },
  process: {
    send(input) {
      return sendAction("process.send", input);
    },
    create(input) {
      return sendAction("process.create", input);
    },
  },
  environment: {
    load(input) {
      return sendAction("environment.load", input);
    },
    saveSecret(input) {
      return saveSecret(input);
    },
  },
  model: {
    catalog() {
      return sendAction("model.catalog", {});
    },
    configure(input) {
      return sendAction("model.configure", input);
    },
  },
  stop() {
    ipcRenderer.send("connection:stop");
  },
  onEvent(callback) {
    const listener = (_event, kernelEvent) => {
      callback(kernelEvent);
    };
    ipcRenderer.on("kernel:event", listener);
    return () => {
      ipcRenderer.removeListener("kernel:event", listener);
    };
  },
});
