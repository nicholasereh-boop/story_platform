import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

// Source scans that keep the security rules true as the code grows. They read the real files, so a careless change
// elsewhere in the project fails here.
const HERE = path.dirname(fileURLToPath(import.meta.url));
const SRC = path.resolve(HERE, "..");
const ROOT = path.resolve(SRC, "..");

function walk(dir) {
  return fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) return entry.name === "__tests__" || entry.name === "node_modules" ? [] : walk(full);
    return /\.(js|jsx)$/.test(entry.name) ? [full] : [];
  });
}
const files = walk(SRC).map((file) => ({ file: path.relative(ROOT, file), text: fs.readFileSync(file, "utf8") }));

// Comments may mention the forbidden names (this very rule is explained in comments), so look at code only.
const code = (text) => text.replace(/\/\*[\s\S]*?\*\//g, "").replace(/(^|[^:])\/\/.*$/gm, "$1");

describe("no raw HTML injection", () => {
  const FORBIDDEN = /dangerouslySetInnerHTML|\.innerHTML|\.outerHTML|insertAdjacentHTML|document\.write\(|\beval\(|new Function\(/;

  it("finds source files to scan", () => {
    expect(files.length).toBeGreaterThan(40);
  });

  it("uses none of the HTML-injecting APIs anywhere in src/", () => {
    const hits = files.filter(({ text }) => FORBIDDEN.test(code(text))).map(({ file }) => file);
    expect(hits).toEqual([]);
  });

  it("renders JSON-LD through textContent only (the one escaped helper)", () => {
    const users = files.filter(({ text }) => /application\/ld\+json/.test(code(text)));
    expect(users.length).toBeGreaterThan(0);
    for (const { file, text } of users) {
      expect(code(text), file).toMatch(/safeJsonLd|textContent/);
    }
  });
});

describe("no secrets or tokens in the frontend", () => {
  it("never references a server-side secret name", () => {
    const SECRET = /GOOGLE_CLIENT_SECRET|SECRET_KEY|MFA_ENCRYPTION_KEY|DJANGO_SECRET|[A-Z_]*_SECRET\b|[A-Z_]*_PASSWORD\b/;
    const configs = ["vite.config.js", "index.html", ".env.example"].filter((f) => fs.existsSync(path.join(ROOT, f)))
      .map((f) => ({ file: f, text: fs.readFileSync(path.join(ROOT, f), "utf8") }));
    const hits = [...files, ...configs].filter(({ text }) => SECRET.test(code(text))).map(({ file }) => file);
    expect(hits).toEqual([]);
  });

  it("only exposes VITE_ variables that are not secrets", () => {
    const env = path.join(ROOT, ".env.example");
    if (!fs.existsSync(env)) return;
    const names = fs.readFileSync(env, "utf8").split("\n").map((l) => l.split("=")[0].trim()).filter((n) => n && !n.startsWith("#"));
    for (const name of names) expect(name).toMatch(/^VITE_/);
    for (const name of names) expect(name).not.toMatch(/SECRET|PASSWORD|TOKEN|PRIVATE/);
  });

  it("never writes a token or password to web storage", () => {
    const WRITE = /(localStorage|sessionStorage)\.setItem\(\s*([^,)]+)/g;
    for (const { file, text } of files) {
      for (const match of code(text).matchAll(WRITE)) {
        expect(match[2].toLowerCase(), `${file}: ${match[0]}`).not.toMatch(/token|password|secret|session[-_]?id|csrf|recovery|otp/);
      }
    }
  });
});

describe("external links", () => {
  it("every target=_blank link carries rel noopener noreferrer", () => {
    for (const { file, text } of files.filter(({ file }) => file.endsWith(".jsx"))) {
      for (const tag of code(text).match(/<a\b[^>]*target="_blank"[^>]*>/g) || []) {
        expect(tag, file).toMatch(/rel="[^"]*noopener[^"]*noreferrer[^"]*"|rel=\{/);
      }
    }
  });
});
