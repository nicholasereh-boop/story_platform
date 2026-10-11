import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// The auth state and the signup prompt are replaced by simple stand-ins.
const auth = { user: null };
const request = vi.fn();
vi.mock("../auth/AuthContext", () => ({ useAuth: () => auth }));
vi.mock("../engagement/SignupPromptContext", () => ({ useSignupPrompt: () => ({ request }) }));
vi.mock("../api/engagement", () => ({ getLikes: vi.fn(), likeStory: vi.fn(), unlikeStory: vi.fn() }));

import * as api from "../api/engagement";
import LikeButton from "../components/engagement/LikeButton";

const reader = { email: "a@example.com", email_verified: true };
const serverError = () => Object.assign(new Error("boom"), { status: 500, friendly: "Could not save your like." });

function show(props = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <LikeButton slug="a-story" initialCount={4} {...props} />
    </QueryClientProvider>
  );
}
const button = () => screen.getByRole("button");

beforeEach(() => {
  vi.clearAllMocks();
  auth.user = reader;
  api.getLikes.mockResolvedValue({ count: 4, liked: false });
});

describe("LikeButton", () => {
  it("updates at once, is disabled while the request is pending, and keeps the server's answer", async () => {
    let finish;
    api.likeStory.mockReturnValue(new Promise((resolve) => { finish = resolve; }));
    show();
    await waitFor(() => expect(api.getLikes).toHaveBeenCalledWith("a-story"));
    expect(button().getAttribute("aria-pressed")).toBe("false");

    fireEvent.click(button());
    await waitFor(() => expect(button().getAttribute("aria-pressed")).toBe("true")); // optimistic
    expect(screen.getByText("5 likes")).toBeTruthy();
    expect(button().disabled).toBe(true); // no double clicks while pending

    finish({ count: 5, liked: true });
    await waitFor(() => expect(button().disabled).toBe(false));
    expect(button().getAttribute("aria-pressed")).toBe("true");
    expect(api.likeStory).toHaveBeenCalledTimes(1);
  });

  it("rolls back and shows a message when the server refuses", async () => {
    api.likeStory.mockRejectedValue(serverError());
    show();
    await waitFor(() => expect(api.getLikes).toHaveBeenCalled());
    fireEvent.click(button());
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.getByRole("alert").textContent).toBe("Could not save your like.");
    expect(button().getAttribute("aria-pressed")).toBe("false"); // back to the old state
    expect(screen.getByText("4 likes")).toBeTruthy();
    expect(button().disabled).toBe(false);
  });

  it("unlikes with DELETE and rolls back too", async () => {
    api.getLikes.mockResolvedValue({ count: 4, liked: true });
    api.unlikeStory.mockRejectedValue(serverError());
    show();
    await waitFor(() => expect(button().getAttribute("aria-pressed")).toBe("true"));
    fireEvent.click(button());
    await screen.findByRole("alert");
    expect(api.unlikeStory).toHaveBeenCalledWith("a-story");
    expect(button().getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByText("4 likes")).toBeTruthy();
  });

  it("announces the count in a polite live region", () => {
    show();
    const live = screen.getByText("4 likes");
    expect(live.getAttribute("aria-live")).toBe("polite");
  });

  it("opens the signup prompt for an anonymous visitor instead of calling the API", () => {
    auth.user = null;
    show();
    fireEvent.click(button());
    expect(request).toHaveBeenCalledWith("like");
    expect(api.likeStory).not.toHaveBeenCalled();
    expect(api.getLikes).not.toHaveBeenCalled(); // visitors never ask who liked
    expect(screen.getByText("4 likes")).toBeTruthy();
  });
});
