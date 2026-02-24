const fs = require("fs");
const path = require("path");
const { execFile } = require("child_process");
const { promisify } = require("util");
const execFileAsync = promisify(execFile);

module.exports = async function afterPack(context) {
  const appOutDir = context.appOutDir;
  const entries = fs.readdirSync(appOutDir);
  const appName = entries.find((e) => e.endsWith(".app"));
  if (!appName) {
    throw new Error("afterPack: no .app found in " + appOutDir);
  }
  const appPath = path.join(appOutDir, appName);

  const zstdPath = path.join(appPath, "Contents", "Resources", "bin", "macos-arm64", "zstd");
  if (!fs.existsSync(zstdPath)) {
    throw new Error("afterPack: bundled zstd not found at: " + zstdPath);
  }

  try {
    fs.chmodSync(zstdPath, 0o755);
  } catch (e) {
    console.warn("afterPack: chmod failed:", e.message);
  }

  const identity = process.env.CSC_NAME;
  if (!identity) {
    console.warn("afterPack: CSC_NAME not set; skipping codesign for zstd");
    return;
  }

  try {
    console.log("afterPack: codesigning bundled zstd:", zstdPath);
    const signResult = await execFileAsync(
      "/usr/bin/codesign",
      ["--force", "--timestamp", "--options", "runtime", "--sign", identity, zstdPath],
      { env: process.env }
    );
    if (signResult.stdout) console.log("afterPack: codesign stdout:", signResult.stdout);
    if (signResult.stderr) console.error("afterPack: codesign stderr:", signResult.stderr);

    console.log("afterPack: verifying codesign for:", zstdPath);
    const verifyResult = await execFileAsync(
      "/usr/bin/codesign",
      ["-dv", "--verbose=4", zstdPath],
      { env: process.env }
    );
    if (verifyResult.stdout) console.log("afterPack: verify stdout:", verifyResult.stdout);
    if (verifyResult.stderr) console.error("afterPack: verify stderr:", verifyResult.stderr);

    console.log("afterPack: codesigned bundled zstd:", zstdPath);
  } catch (error) {
    console.error("afterPack: codesign failed:", error.message);
    if (error.stdout) console.error("afterPack: stdout:", error.stdout);
    if (error.stderr) console.error("afterPack: stderr:", error.stderr);
    throw error;
  }
};

