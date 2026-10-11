import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";
import { STORAGE_KEYS } from "../privacy/storageKeys";

// Keeps the privacy page's storage table true: every key the code writes to localStorage or sessionStorage must be
// listed in privacy/storageKeys.js, and every listed key must still exist in the code.
const SRC = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");

function walk(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) return entry.name === "__tests__" ? [] : walk(full);
    return /\.(js|jsx)$/.test(entry.name) && entry.name !== "storageKeys.js" ? [full] : [];
  });
}
const sources = walk(SRC).map((file) => fs.readFileSync(file, "utf8"));
const all = sources.join("\n");

// Keys are string constants ("sb.something") or the draft template `storyboard:draft:${id}`.
const literalKeys = [...all.matchAll(/["'`]((?:sb\.|storyboard:)[A-Za-z0-9_.:${}-]*)["'`]/g)].map((m) => m[1].replace(/\$\{[^}]*\}/g, "<story id>"));

describe("storage key table", () => {
  it("finds the keys in the source", () => {
    expect(literalKeys.length).toBeGreaterThanOrEqual(6);
  });

  it("lists every key the code uses", () => {
    const listed = new Set(STORAGE_KEYS.map((k) => k.key));
    for (const key of new Set(literalKeys)) expect(listed.has(key), `${key} is used in the code but missing from storageKeys.js`).toBe(true);
  });

  it("lists nothing the code no longer uses", () => {
    const used = new Set(literalKeys);
    for (const { key } of STORAGE_KEYS) expect(used.has(key), `${key} is listed but not used`).toBe(true);
  });

  it("states storage, purpose, duration and whether it is strictly necessary for each key", () => {
    for (const entry of STORAGE_KEYS) {
      expect(["localStorage", "sessionStorage"]).toContain(entry.storage);
      expect(entry.purpose.length).toBeGreaterThan(10);
      expect(entry.duration.length).toBeGreaterThan(3);
      expect(typeof entry.necessary).toBe("boolean");
    }
  });

  it("never stores a cookie from the frontend", () => {
    expect(all).not.toMatch(/document\.cookie\s*=/);
  });
});
