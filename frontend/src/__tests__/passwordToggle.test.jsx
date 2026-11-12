import { fireEvent, render, screen } from "@testing-library/react";
import { useState } from "react";
import { describe, expect, it } from "vitest";
import PasswordField from "../components/auth/PasswordField";
import PasswordInput from "../components/auth/PasswordInput";

function Demo() {
  const [value, setValue] = useState("secret-123");
  return <PasswordField id="pw" label="Password" autoComplete="current-password" value={value} onChange={setValue} />;
}

describe("show and hide password", () => {
  it("hides the password by default and shows it when the eye button is pressed", () => {
    render(<Demo />);
    const input = screen.getByLabelText("Password");
    expect(input.getAttribute("type")).toBe("password");
    const toggle = screen.getByRole("button", { name: "Show password" });
    expect(toggle.getAttribute("aria-pressed")).toBe("false");
    fireEvent.click(toggle);
    expect(input.getAttribute("type")).toBe("text");
    expect(input.value).toBe("secret-123"); // what was typed is kept
    expect(screen.getByRole("button", { name: "Hide password" }).getAttribute("aria-pressed")).toBe("true");
    fireEvent.click(screen.getByRole("button", { name: "Hide password" }));
    expect(input.getAttribute("type")).toBe("password");
  });

  it("the button never submits the form", () => {
    let submitted = false;
    render(<form onSubmit={(e) => { e.preventDefault(); submitted = true; }}><PasswordInput id="x" defaultValue="a" aria-label="Pw" /></form>);
    fireEvent.click(screen.getByRole("button", { name: "Show password" }));
    expect(submitted).toBe(false);
  });

  it("each box has its own switch", () => {
    render(<><PasswordInput id="a" aria-label="First" /><PasswordInput id="b" aria-label="Second" /></>);
    fireEvent.click(screen.getAllByRole("button", { name: "Show password" })[0]);
    expect(screen.getByLabelText("First").getAttribute("type")).toBe("text");
    expect(screen.getByLabelText("Second").getAttribute("type")).toBe("password");
  });
});
