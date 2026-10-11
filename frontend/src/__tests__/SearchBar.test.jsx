import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router-dom";
import SearchBar from "../components/public/SearchBar";

function Where() {
  const l = useLocation();
  return <p data-testid="where">{l.pathname + l.search}</p>;
}
const setup = (start = "/") =>
  render(
    <MemoryRouter initialEntries={[start]}>
      <SearchBar />
      <Routes><Route path="*" element={<Where />} /></Routes>
    </MemoryRouter>
  );
const type = (text) => fireEvent.change(screen.getByRole("searchbox"), { target: { value: text } });
const submit = () => fireEvent.submit(screen.getByRole("search"));

describe("SearchBar", () => {
  it("goes to /search?q= with the text trimmed and encoded", () => {
    setup();
    type("  light house & sea  ");
    submit();
    expect(screen.getByTestId("where").textContent).toBe("/search?q=light%20house%20%26%20sea");
  });

  it("ignores an empty or blank submit", () => {
    setup("/stories");
    type("   ");
    submit();
    expect(screen.getByTestId("where").textContent).toBe("/stories");
  });

  it("shows the current query on the results page", () => {
    setup("/search?q=lamp");
    expect(screen.getByRole("searchbox").value).toBe("lamp");
  });

  it("has an accessible label and landmark", () => {
    setup();
    expect(screen.getByRole("search")).toBeTruthy();
    expect(screen.getByLabelText("Search stories")).toBeTruthy();
  });
});
