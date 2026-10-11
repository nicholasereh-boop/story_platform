import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import CommentForm, { COMMENT_MAX } from "../components/engagement/CommentForm";

const type = (value) => fireEvent.change(screen.getByRole("textbox"), { target: { value } });
const post = () => screen.getByRole("button", { name: "Post comment" });
const rejection = (status, friendly) => Object.assign(new Error("x"), { status, friendly });

describe("CommentForm", () => {
  it("shows a live character counter out of 2000", () => {
    render(<CommentForm onSubmit={vi.fn()} />);
    expect(screen.getByText(`0 / ${COMMENT_MAX}`)).toBeTruthy();
    type("hello");
    expect(screen.getByText(`5 / ${COMMENT_MAX}`)).toBeTruthy();
  });

  it("cannot post an empty or whitespace-only comment", () => {
    const onSubmit = vi.fn();
    render(<CommentForm onSubmit={onSubmit} />);
    expect(post().disabled).toBe(true);
    type("   \n  ");
    expect(post().disabled).toBe(true);
    fireEvent.submit(screen.getByRole("textbox").closest("form"));
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("blocks more than 2000 characters and marks the counter", () => {
    const onSubmit = vi.fn();
    render(<CommentForm onSubmit={onSubmit} />);
    type("x".repeat(COMMENT_MAX + 1));
    expect(post().disabled).toBe(true);
    expect(screen.getByText(`${COMMENT_MAX + 1} / ${COMMENT_MAX}`).className).toContain("over");
    type("x".repeat(COMMENT_MAX));
    expect(post().disabled).toBe(false);
  });

  it("sends the text and clears the box", async () => {
    const onSubmit = vi.fn().mockResolvedValue({});
    render(<CommentForm onSubmit={onSubmit} />);
    type("A thoughtful reply");
    fireEvent.click(post());
    await waitFor(() => expect(screen.getByRole("textbox").value).toBe(""));
    expect(onSubmit).toHaveBeenCalledWith("A thoughtful reply");
  });

  it("keeps the text and shows the server's message for 400 and 403", async () => {
    const onSubmit = vi.fn().mockRejectedValueOnce(rejection(400, "Comments can contain at most 2 links.")).mockRejectedValueOnce(rejection(403, "Please verify your email address first."));
    render(<CommentForm onSubmit={onSubmit} />);
    type("see http://a http://b http://c");
    fireEvent.click(post());
    expect((await screen.findByRole("alert")).textContent).toBe("Comments can contain at most 2 links.");
    expect(screen.getByRole("textbox").value).toBe("see http://a http://b http://c");
    fireEvent.click(post());
    await waitFor(() => expect(screen.getByRole("alert").textContent).toBe("Please verify your email address first."));
  });

  it("shows a plain message for 429 (too many comments)", async () => {
    render(<CommentForm onSubmit={vi.fn().mockRejectedValue(rejection(429, "Request was throttled. Expected available in 3000 seconds."))} />);
    type("hi");
    fireEvent.click(post());
    expect((await screen.findByRole("alert")).textContent).toMatch(/too often/i);
  });
});
