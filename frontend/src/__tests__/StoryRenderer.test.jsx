import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import StoryRenderer from "../components/StoryRenderer";

const doc = (...content) => ({ type: "doc", content });
const text = (t, marks) => ({ type: "text", text: t, ...(marks ? { marks } : {}) });
const para = (...c) => ({ type: "paragraph", content: c });
const html = (content) => render(<StoryRenderer content={content} />).container;

describe("StoryRenderer", () => {
  it("renders paragraphs, headings (with alignment) and breaks", () => {
    const c = html(doc(
      { type: "heading", attrs: { level: 3, textAlign: "center" }, content: [text("Title")] },
      para(text("Hello"), { type: "hardBreak" }, text("world")),
    ));
    const h = c.querySelector("h3");
    expect(h.textContent).toBe("Title");
    expect(h.className).toContain("ta-center");
    expect(c.querySelector("p br")).toBeTruthy();
  });

  it("renders every mark", () => {
    const c = html(doc(para(
      text("b", [{ type: "bold" }]), text("i", [{ type: "italic" }]), text("u", [{ type: "underline" }]), text("s", [{ type: "strike" }]),
    )));
    ["strong", "em", "u", "s"].forEach((tag) => expect(c.querySelector(tag)).toBeTruthy());
  });

  it("renders lists, blockquote and horizontal rule", () => {
    const li = (t) => ({ type: "listItem", content: [para(text(t))] });
    const c = html(doc(
      { type: "bulletList", content: [li("a"), li("b")] },
      { type: "orderedList", attrs: { start: 3 }, content: [li("c")] },
      { type: "blockquote", content: [para(text("quote"))] },
      { type: "horizontalRule" },
    ));
    expect(c.querySelectorAll("ul > li")).toHaveLength(2);
    expect(c.querySelector("ol").getAttribute("start")).toBe("3");
    expect(c.querySelector("blockquote").textContent).toBe("quote");
    expect(c.querySelector("hr")).toBeTruthy();
  });

  it("renders an image as figure/img/figcaption with align and size classes", () => {
    const c = html(doc({ type: "image", attrs: { assetId: 1, src: "/media/a.jpg", alt: "A lighthouse", caption: "At dusk", align: "left", size: "small" } }));
    const fig = c.querySelector("figure");
    expect(fig.className).toContain("img-left");
    expect(fig.className).toContain("img-small");
    expect(fig.querySelector("img").getAttribute("alt")).toBe("A lighthouse");
    expect(fig.querySelector("img").getAttribute("src")).toBe("/media/a.jpg");
    expect(fig.querySelector("figcaption").textContent).toBe("At dusk");
  });

  it("does not render images without a safe src", () => {
    expect(html(doc({ type: "image", attrs: { assetId: 1 } })).querySelector("img")).toBeNull();
    expect(html(doc({ type: "image", attrs: { assetId: 1, src: "javascript:alert(1)" } })).querySelector("img")).toBeNull();
  });

  it("renders YouTube as a youtube-nocookie iframe and ignores a bad id", () => {
    const ok = html(doc({ type: "youtube", attrs: { videoId: "dQw4w9WgXcQ" } })).querySelector("iframe");
    expect(ok.getAttribute("src")).toBe("https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ");
    expect(ok.getAttribute("loading")).toBe("lazy");
    expect(html(doc({ type: "youtube", attrs: { videoId: "x\" onload=\"y" } })).querySelector("iframe")).toBeNull();
  });

  it("gives safe links target=_blank and rel=noopener noreferrer nofollow", () => {
    const a = html(doc(para(text("go", [{ type: "link", attrs: { href: "https://example.com" } }])))).querySelector("a");
    expect(a.getAttribute("href")).toBe("https://example.com");
    expect(a.getAttribute("target")).toBe("_blank");
    expect(a.getAttribute("rel")).toBe("noopener noreferrer nofollow");
    const mail = html(doc(para(text("m", [{ type: "link", attrs: { href: "mailto:a@b.co" } }])))).querySelector("a");
    expect(mail.getAttribute("href")).toBe("mailto:a@b.co");
  });

  it("drops javascript: and data: links but keeps the words", () => {
    ["javascript:alert(1)", "data:text/html,x", " https://x.com"].forEach((href) => {
      const c = html(doc(para(text("click me", [{ type: "link", attrs: { href } }]))));
      expect(c.querySelector("a")).toBeNull();
      expect(c.textContent).toBe("click me");
    });
  });

  it("ignores unknown nodes (and their children) and unknown marks", () => {
    const c = html(doc(
      { type: "script", content: [para(text("EVIL"))] },
      { type: "iframe", attrs: { src: "https://evil.com" } },
      para(text("kept", [{ type: "sparkle" }])),
    ));
    expect(c.textContent).toBe("kept");
    expect(c.querySelector("iframe")).toBeNull();
  });

  it("never turns text into HTML", () => {
    const c = html(doc(para(text('<img src=x onerror="alert(1)"><script>alert(2)</script>'))));
    expect(c.querySelector("img")).toBeNull();
    expect(c.querySelector("script")).toBeNull();
    expect(c.textContent).toContain("<script>alert(2)</script>");
  });

  it("renders nothing for an empty or invalid document", () => {
    expect(html(null).textContent).toBe("");
    expect(html({ type: "doc" }).textContent).toBe("");
  });
});
