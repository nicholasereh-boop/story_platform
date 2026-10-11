import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import ShareButtons, { shareLinks } from "../components/public/ShareButtons";

describe("shareLinks", () => {
  it("encodes the address and the title", () => {
    const links = shareLinks("https://x.com/stories/a?b=1&c=2", "Tom & Jerry's #1 <story>");
    expect(links.x).toBe(
      "https://twitter.com/intent/tweet?url=https%3A%2F%2Fx.com%2Fstories%2Fa%3Fb%3D1%26c%3D2&text=Tom%20%26%20Jerry's%20%231%20%3Cstory%3E"
    );
    expect(links.facebook).toBe("https://www.facebook.com/sharer/sharer.php?u=https%3A%2F%2Fx.com%2Fstories%2Fa%3Fb%3D1%26c%3D2");
  });

  it("cannot be tricked into adding parameters", () => {
    const links = shareLinks("https://x.com/a", "hello&url=https://evil.com");
    expect(links.x.split("&")).toHaveLength(2); // only url= and text=
  });
});

describe("ShareButtons", () => {
  it("renders safe external links", () => {
    render(<ShareButtons url="https://x.com/stories/a" title="A story" />);
    for (const name of [/Share on X/i, /Share on Facebook/i]) {
      const a = screen.getByRole("link", { name });
      expect(a.getAttribute("target")).toBe("_blank");
      expect(a.getAttribute("rel")).toBe("noopener noreferrer");
    }
  });

  it("copies the link and says so", async () => {
    const writeText = vi.fn().mockResolvedValue();
    Object.assign(navigator, { clipboard: { writeText } });
    render(<ShareButtons url="https://x.com/stories/a" title="A story" />);
    fireEvent.click(screen.getByRole("button", { name: /copy link/i }));
    expect(await screen.findByText("Link copied.")).toBeTruthy();
    expect(writeText).toHaveBeenCalledWith("https://x.com/stories/a");
  });

  it("tells the person when copying is not possible", async () => {
    Object.assign(navigator, { clipboard: { writeText: vi.fn().mockRejectedValue(new Error("no")) } });
    render(<ShareButtons url="https://x.com/a" title="A" />);
    fireEvent.click(screen.getByRole("button", { name: /copy link/i }));
    expect(await screen.findByText(/could not copy/i)).toBeTruthy();
  });
});
