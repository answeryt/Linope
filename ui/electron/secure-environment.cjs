const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

class SecureEnvironmentFile {
  constructor() {
    this.directory = null;
    this.file = null;
  }

  write(key, value) {
    if (
      typeof key !== "string" ||
      !key ||
      key.includes("=") ||
      /[\s\0]/.test(key) ||
      typeof value !== "string" ||
      /[\r\n\0]/.test(value)
    ) {
      throw new Error("Invalid environment secret");
    }
    if (!this.directory) {
      this.directory = fs.mkdtempSync(path.join(os.tmpdir(), "linope-env-"));
    }
    this.file = path.join(this.directory, "model.env");
    fs.writeFileSync(this.file, `${key}=${value}\n`, {
      encoding: "utf8",
      mode: 0o600,
    });
    return this.file;
  }

  cleanup() {
    if (this.file) {
      try {
        fs.rmSync(this.file, { force: true });
      } catch {}
      this.file = null;
    }
    if (this.directory) {
      try {
        fs.rmSync(this.directory, { recursive: true, force: true });
      } catch {}
      this.directory = null;
    }
  }
}

module.exports = { SecureEnvironmentFile };
