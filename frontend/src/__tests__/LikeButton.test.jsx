import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

// The auth state is replaced by a simple stand-in (the signup prompt is NOT involved in liking any more).
const auth = { user: null };
vi.mock("../auth/AuthContext", () => ({ useAuth: () => auth }));
vi.mock("../api/engagement", () => ({ getLikes: vi.fn(), likeStory: vi.fn(), unlikeStory: vi.fn() }));

import * as api from "../api/engagement";
import LikeButton from "../components/engagement/LikeButton";

const reader = { email: "a@example.com" };
const serverError = () => Object.assign(new Error("boom"), { status: 500, friendly: "Could not save your like." });

function show(props = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return { client, ...render(
    <QueryClientProvider client={client}>
      <LikeButton slug="a-story" initialCount={4} {...props} />
    </QueryClientProvider>
  ) };
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

  describe("a visitor who is not logged in", () => {
    beforeEach(() => {
      auth.user = null;
    });

    it("can like: the request goes to the server straight away, with no signup prompt in the way", async () => {
      api.likeStory.mockResolvedValue({ count: 5, liked: true });
      show();
      await waitFor(() => expect(api.getLikes).toHaveBeenCalledWith("a-story")); // visitors ask who liked, too
      fireEvent.click(button());
      await waitFor(() => expect(api.likeStory).toHaveBeenCalledWith("a-story"));
      await waitFor(() => expect(button().getAttribute("aria-pressed")).toBe("true"));
      expect(screen.getByText("5 likes")).toBeTruthy();
      expect(screen.getByRole("button").textContent).toMatch(/Liked/);
      expect(screen.queryByRole("dialog")).toBeNull();
    });

    it("sees Liked again after a reload, because the server remembers this browser", async () => {
      api.getLikes.mockResolvedValue({ count: 9, liked: true });
      show({ initialCount: 8 });
      await waitFor(() => expect(button().getAttribute("aria-pressed")).toBe("true"));
      expect(screen.getByText("9 likes")).toBeTruthy();
    });

    it("can unlike", async () => {
      api.getLikes.mockResolvedValue({ count: 3, liked: true });
      api.unlikeStory.mockResolvedValue({ count: 2, liked: false });
      show();
      await waitFor(() => expect(button().getAttribute("aria-pressed")).toBe("true"));
      fireEvent.click(button());
      await waitFor(() => expect(api.unlikeStory).toHaveBeenCalledWith("a-story"));
      await waitFor(() => expect(screen.getByText("2 likes")).toBeTruthy());
      expect(button().getAttribute("aria-pressed")).toBe("false");
    });

    it("rolls back with a plain message when the visitor limit is reached (429)", async () => {
      api.likeStory.mockRejectedValue(Object.assign(new Error("throttled"), { status: 429, friendly: "Expected available in 60 seconds." }));
      show();
      await waitFor(() => expect(api.getLikes).toHaveBeenCalled());
      fireEvent.click(button());
      expect((await screen.findByRole("alert")).textContent).toMatch(/too often/i);
      expect(button().getAttribute("aria-pressed")).toBe("false");
      expect(screen.getByText("4 likes")).toBeTruthy();
    });

    it("looks the story up again when the person logs in, so a like made as a visitor still shows", async () => {
      api.getLikes.mockResolvedValueOnce({ count: 4, liked: false }).mockResolvedValue({ count: 4, liked: true });
      const view = show();
      await waitFor(() => expect(api.getLikes).toHaveBeenCalledTimes(1));
      auth.user = { id: 7, email: "a@example.com" };
      view.rerender(
        <QueryClientProvider client={view.client}>
          <LikeButton slug="a-story" initialCount={4} />
        </QueryClientProvider>
      );
      await waitFor(() => expect(api.getLikes).toHaveBeenCalledTimes(2));
      await waitFor(() => expect(button().getAttribute("aria-pressed")).toBe("true"));
    });
  });
});
