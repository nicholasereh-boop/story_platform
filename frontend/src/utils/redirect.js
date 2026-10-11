// Where to go after logging in. `from` comes from router state (set by our own guards), but it is still checked:
// only same-site paths are allowed, never "//evil.example" or a full URL.
export function safeFrom(from) {
  return typeof from === "string" && from.startsWith("/") && !from.startsWith("//") && !from.includes("\\") ? from : null;
}

// Staff land on the admin by default; readers on the home page. A valid `from` wins for both.
export function afterLoginPath(user, from) {
  return safeFrom(from) || (user?.is_staff ? "/admin/stories" : "/");
}
