import { describe, expect, it } from "vitest";
import { MIN_PASSWORD_LENGTH, passwordProblem, passwordProblems } from "../utils/password";

describe("password rules (mirror of the server's validators)", () => {
  it("accepts a long, uncommon password", () => {
    expect(passwordProblems("Correct-horse-battery-9", "me@example.com")).toEqual([]);
  });

  it("requires the minimum length", () => {
    expect(MIN_PASSWORD_LENGTH).toBe(10);
    expect(passwordProblem("Short-9x")).toMatch(/at least 10/);
    expect(passwordProblem("Exactly-10")).toBe("");
  });

  it("rejects all-numeric passwords", () => {
    expect(passwordProblems("98765432101234")).toContain("The password cannot be only numbers.");
  });

  it("rejects very common passwords", () => {
    expect(passwordProblems("password123")).toContain("That password is too common.");
  });

  it("rejects a password that contains the email name", () => {
    expect(passwordProblem("xx-nicholas-xx-9", "nicholas@example.com")).toMatch(/similar to your email/);
    expect(passwordProblem("xx-nicholas-xx-9", "")).toBe("");
  });
});
