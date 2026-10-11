// Client-side mirror of the server's password rules (backend AUTH_PASSWORD_VALIDATORS), so people see problems
// before submitting. The SERVER stays the authority: it may still reject a password this accepts, and its
// message is shown when it does.
export const MIN_PASSWORD_LENGTH = 10;

// A tiny sample of the very common passwords Django's CommonPasswordValidator rejects.
const COMMON = new Set([
  "password", "password1", "password123", "1234567890", "12345678910", "qwertyuiop", "qwerty12345", "iloveyou123",
  "letmein1234", "welcome1234", "admin12345", "abc1234567", "0123456789", "1q2w3e4r5t", "passw0rd123",
]);

// Returns a list of problems (empty = looks fine). `email` enables the "too similar to your email" check.
export function passwordProblems(password, email = "") {
  const problems = [];
  const value = password || "";
  if (value.length < MIN_PASSWORD_LENGTH) problems.push(`Use at least ${MIN_PASSWORD_LENGTH} characters.`);
  if (value && /^[0-9]+$/.test(value)) problems.push("The password cannot be only numbers.");
  if (value && COMMON.has(value.toLowerCase())) problems.push("That password is too common.");
  const local = (email || "").split("@")[0].toLowerCase();
  if (value && local.length >= 4 && value.toLowerCase().includes(local)) problems.push("The password is too similar to your email address.");
  return problems;
}

export const passwordProblem = (password, email) => passwordProblems(password, email)[0] || "";
