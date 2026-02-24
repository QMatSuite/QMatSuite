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

  const libDir = path.join(appPath, "Contents", "Resources", "lib", "macos-arm64");
  if (!fs.existsSync(libDir)) {
    throw new Error("afterPack: lib directory not found at: " + libDir + " (bundling is broken)");
  }

  // Find libzstd dylib
  const libFiles = fs.readdirSync(libDir);
  const libZstdFiles = libFiles.filter((f) => f.startsWith("libzstd") && f.endsWith(".dylib"));
  if (libZstdFiles.length === 0) {
    throw new Error("afterPack: libzstd dylib not found at: " + libDir + " (bundling is broken)");
  }

  // Prefer libzstd.1.dylib if present, otherwise use first match
  const libZstdName = libZstdFiles.find((f) => f === "libzstd.1.dylib") || libZstdFiles[0];
  const libZstdPath = path.join(libDir, libZstdName);
  console.log("afterPack: found libzstd dylib:", libZstdPath);

  try {
    fs.chmodSync(zstdPath, 0o755);
  } catch (e) {
    console.warn("afterPack: chmod failed:", e.message);
  }

  // Add rpath: @executable_path/../../lib/macos-arm64
  try {
    console.log("afterPack: adding rpath to zstd");
    await execFileAsync(
      "/usr/bin/install_name_tool",
      ["-add_rpath", "@executable_path/../../lib/macos-arm64", zstdPath],
      { env: process.env }
    );
  } catch (e) {
    // Ignore if rpath already exists (would duplicate error)
    const stderr = (e.stderr || "").toString();
    if (!stderr.includes("would duplicate") && !stderr.includes("already has LC_RPATH")) {
      console.warn("afterPack: install_name_tool -add_rpath failed:", e.message);
    }
  }

  // Check and rewrite libzstd library reference to use @rpath
  try {
    console.log("afterPack: checking library references in zstd");
    const otoolResult = await execFileAsync(
      "/usr/bin/otool",
      ["-L", zstdPath],
      { env: process.env, encoding: "utf-8" }
    );
    const otoolOutput = (otoolResult.stdout || "").toString();
    const lines = otoolOutput.split("\n");
    
    // Determine desired target path: prefer libzstd.1.dylib if it exists
    const targetName = libZstdFiles.includes("libzstd.1.dylib") ? "libzstd.1.dylib" : libZstdName;
    const desiredPath = "@rpath/" + targetName;
    
    for (const line of lines) {
      if (line.includes("libzstd")) {
        // Extract the referenced path (first column, before whitespace)
        const match = line.match(/^\s*(\S+)/);
        if (match) {
          const oldPath = match[1];
          
          if (oldPath !== desiredPath) {
            console.log("afterPack: rewriting libzstd reference from", oldPath, "to", desiredPath);
            await execFileAsync(
              "/usr/bin/install_name_tool",
              ["-change", oldPath, desiredPath, zstdPath],
              { env: process.env }
            );
          } else {
            console.log("afterPack: libzstd reference already correct:", desiredPath);
          }
          break;
        }
      }
    }
  } catch (e) {
    console.warn("afterPack: failed to check/rewrite library references:", e.message);
  }

  // Debug: print LC_RPATH entries to confirm rpath
  try {
    console.log("afterPack: dumping LC_RPATH for zstd");
    const otoolLoadResult = await execFileAsync(
      "/usr/bin/otool",
      ["-l", zstdPath],
      { env: process.env, encoding: "utf-8" }
    );
    const loadOutput = (otoolLoadResult.stdout || "").toString();
    console.log("afterPack: otool -l zstd (filtered LC_RPATH):");
    // Simple filter: print lines containing LC_RPATH and following two lines for context
    const lcLines = loadOutput.split("\n");
    for (let i = 0; i < lcLines.length; i++) {
      if (lcLines[i].includes("LC_RPATH")) {
        console.log(lcLines[i]);
        if (i + 1 < lcLines.length) console.log(lcLines[i + 1]);
        if (i + 2 < lcLines.length) console.log(lcLines[i + 2]);
      }
    }
  } catch (e) {
    console.warn("afterPack: failed to dump LC_RPATH for zstd:", e.message);
  }

  const identity = process.env.CSC_NAME;
  if (!identity) {
    console.warn("afterPack: CSC_NAME not set; skipping codesign (rpath modifications completed)");
    return;
  }

  try {
    // Codesign ALL libzstd dylibs first
    console.log("afterPack: codesigning libzstd dylibs in", libDir);
    for (const dylibFile of libZstdFiles) {
      const dylibPath = path.join(libDir, dylibFile);
      console.log("afterPack: codesigning", dylibPath);
      const libSignResult = await execFileAsync(
        "/usr/bin/codesign",
        ["--force", "--timestamp", "--options", "runtime", "--sign", identity, dylibPath],
        { env: process.env }
      );
      if (libSignResult.stdout) console.log("afterPack: codesign stdout:", libSignResult.stdout);
      if (libSignResult.stderr) console.error("afterPack: codesign stderr:", libSignResult.stderr);
    }

    // Codesign zstd binary
    console.log("afterPack: codesigning bundled zstd:", zstdPath);
    const signResult = await execFileAsync(
      "/usr/bin/codesign",
      ["--force", "--timestamp", "--options", "runtime", "--sign", identity, zstdPath],
      { env: process.env }
    );
    if (signResult.stdout) console.log("afterPack: codesign stdout:", signResult.stdout);
    if (signResult.stderr) console.error("afterPack: codesign stderr:", signResult.stderr);

    // Verify codesign for one dylib and zstd
    console.log("afterPack: verifying codesign for libzstd:", libZstdPath);
    const libVerifyResult = await execFileAsync(
      "/usr/bin/codesign",
      ["-dv", "--verbose=4", libZstdPath],
      { env: process.env }
    );
    if (libVerifyResult.stdout) console.log("afterPack: libzstd verify stdout:", libVerifyResult.stdout);
    if (libVerifyResult.stderr) console.error("afterPack: libzstd verify stderr:", libVerifyResult.stderr);

    console.log("afterPack: verifying codesign for zstd:", zstdPath);
    const verifyResult = await execFileAsync(
      "/usr/bin/codesign",
      ["-dv", "--verbose=4", zstdPath],
      { env: process.env }
    );
    if (verifyResult.stdout) console.log("afterPack: verify stdout:", verifyResult.stdout);
    if (verifyResult.stderr) console.error("afterPack: verify stderr:", verifyResult.stderr);

    console.log("afterPack: codesigned bundled zstd and libzstd");
  } catch (error) {
    console.error("afterPack: codesign failed:", error.message);
    if (error.stdout) console.error("afterPack: stdout:", error.stdout);
    if (error.stderr) console.error("afterPack: stderr:", error.stderr);
    throw error;
  }
};

