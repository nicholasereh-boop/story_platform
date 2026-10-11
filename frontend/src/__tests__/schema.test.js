import { describe, expect, it } from "vitest";
import { emptyDoc, fromServerDoc, toServerDoc } from "../editor/schema";

// What the editor holds for an image: server attrs PLUS display-only src/width/height.
const editorDoc = () => ({
  type: "doc",
  content: [
    { type: "heading", attrs: { level: 2, textAlign: "center" }, content: [{ type: "text", text: "Hi" }] },
    { type: "paragraph", attrs: { textAlign: "left" }, content: [
      { type: "text", text: "link", marks: [{ type: "bold" }, { type: "link", attrs: { href: "https://a.com", target: "_blank", rel: "noopener", class: null } }] },
    ] },
    { type: "image", attrs: { assetId: 7, alt: "A", caption: "C", align: "left", size: "small", src: "/media/x.jpg", width: 800, height: 600 } },
    { type: "youtube", attrs: { videoId: "dQw4w9WgXcQ" } },
    { type: "orderedList", attrs: { start: 1, type: null }, content: [{ type: "listItem", content: [{ type: "paragraph" }] }] },
  ],
});

describe("toServerDoc", () => {
  it("strips src, width and height from images but keeps the five server attrs", () => {
    const img = toServerDoc(editorDoc()).content[2];
    expect(img.attrs).toEqual({ assetId: 7, alt: "A", caption: "C", align: "left", size: "small" });
  });

  it("keeps only href on links", () => {
    const mark = toServerDoc(editorDoc()).content[1].content[0].marks[1];
    expect(mark).toEqual({ type: "link", attrs: { href: "https://a.com" } });
  });

  it("keeps schema attributes such as level and textAlign, and the youtube id", () => {
    const doc = toServerDoc(editorDoc());
    expect(doc.content[0].attrs).toEqual({ level: 2, textAlign: "center" });
    expect(doc.content[3].attrs).toEqual({ videoId: "dQw4w9WgXcQ" });
  });

  it("drops attributes the server does not know", () => {
    const doc = toServerDoc({ type: "doc", content: [{ type: "paragraph", attrs: { style: "x", onclick: "y" } }] });
    expect(doc.content[0].attrs).toBeUndefined();
  });

  it("does not modify its input", () => {
    const input = editorDoc();
    const copy = JSON.stringify(input);
    toServerDoc(input);
    expect(JSON.stringify(input)).toBe(copy);
  });

  it("returns an empty document for junk input", () => {
    expect(toServerDoc(null)).toEqual(emptyDoc());
    expect(toServerDoc({ type: "paragraph" })).toEqual(emptyDoc());
  });
});

describe("fromServerDoc", () => {
  it("keeps what the server sent, including src/width/height", () => {
    const server = { type: "doc", content: [{ type: "image", attrs: { assetId: 7, alt: "A", caption: "", align: "left", size: "small", src: "/media/x.jpg", width: 800, height: 600 } }] };
    expect(fromServerDoc(server).content[0].attrs).toEqual(server.content[0].attrs);
  });

  it("fills image defaults that are missing", () => {
    const doc = fromServerDoc({ type: "doc", content: [{ type: "image", attrs: { assetId: 1 } }] });
    expect(doc.content[0].attrs).toMatchObject({ assetId: 1, align: "center", size: "full", alt: "", caption: "" });
  });

  it("round-trips: fromServerDoc then toServerDoc removes the display attrs again", () => {
    const server = { type: "doc", content: [{ type: "image", attrs: { assetId: 3, alt: "", caption: "", align: "center", size: "full", src: "/m/a.png", width: 1, height: 2 } }] };
    expect(toServerDoc(fromServerDoc(server)).content[0].attrs).toEqual({ assetId: 3, alt: "", caption: "", align: "center", size: "full" });
  });

  it("gives an empty paragraph to empty or invalid documents", () => {
    expect(fromServerDoc(undefined)).toEqual(emptyDoc());
    expect(fromServerDoc({ type: "doc", content: [] }).content).toEqual([{ type: "paragraph" }]);
  });
});
