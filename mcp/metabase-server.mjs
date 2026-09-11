#!/usr/bin/env node
/**
 * Thin launcher for the Metabase MCP server: loads METABASE_API_KEY from
 * the repo-root .env (gitignored, never committed) into the environment,
 * then execs the real server package directly - avoiding an extra
 * dotenv-cli npm resolution hop on every MCP startup.
 */
import { spawn } from "node:child_process";
import { readFileSync, existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import path from "node:path";

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const envPath = path.join(repoRoot, ".env");

if (existsSync(envPath)) {
  for (const line of readFileSync(envPath, "utf8").split(/\r?\n/)) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;

    const eq = trimmed.indexOf("=");
    if (eq === -1) continue;

    const key = trimmed.slice(0, eq).trim();
    const value = trimmed.slice(eq + 1).trim();

    if (key && !(key in process.env)) {
      process.env[key] = value;
    }
  }
}

const npxCmd = process.platform === "win32" ? "npx.cmd" : "npx";

const child = spawn(npxCmd, ["-y", "@easecloudio/mcp-metabase-server"], {
  stdio: "inherit",
  env: process.env,
  shell: process.platform === "win32",
});

child.on("exit", (code) => process.exit(code ?? 1));
