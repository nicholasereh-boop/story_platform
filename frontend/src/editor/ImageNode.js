import { Node } from "@tiptap/core";

// Custom "image" node. It matches the server schema: assetId, alt, caption, align, size are PERSISTED.
// src, width, height are display-only attributes the server resolves for us; toServerDoc() strips them
// before saving, so the editor can show the picture without the client ever storing a URL.

const ALIGNS = ["left", "center", "right"];
const SIZES = ["small", "medium", "full"];
const oneOf = (value, list, fallback) => (list.includes(value) ? value : fallback);

export const ImageNode = Node.create({
  name: "image",
  group: "block",
  atom: true, // one unit: edited through the "Image settings" panel, not typed into
  draggable: true,

  addAttributes() {
    return {
      assetId: {
        default: null,
        parseHTML: (el) => {
          const id = Number(el.getAttribute("data-asset-id"));
          return Number.isInteger(id) && id > 0 ? id : null;
        },
      },
      alt: { default: "", parseHTML: (el) => el.querySelector("img")?.getAttribute("alt") || "" },
      caption: { default: "", parseHTML: (el) => el.querySelector("figcaption")?.textContent || "" },
      align: { default: "center", parseHTML: (el) => oneOf(el.getAttribute("data-align"), ALIGNS, "center") },
      size: { default: "full", parseHTML: (el) => oneOf(el.getAttribute("data-size"), SIZES, "full") },
      // display-only (never saved)
      src: { default: null, parseHTML: (el) => el.querySelector("img")?.getAttribute("src") || null },
      width: { default: null, parseHTML: () => null },
      height: { default: null, parseHTML: () => null },
    };
  },

  // Only OUR figure (it carries data-asset-id) is accepted from pasted HTML. A random <img> from a web page has no
  // asset id, matches nothing here, and is dropped: nothing outside the media library can enter a story.
  parseHTML() {
    return [{ tag: "figure[data-asset-id]" }];
  },

  renderHTML({ node }) {
    const { assetId, alt, caption, align, size, src } = node.attrs;
    return [
      "figure",
      { class: `story-image img-${align} img-${size}`, "data-asset-id": assetId, "data-align": align, "data-size": size },
      ["img", { src: src || "", alt: alt || "" }],
      ...(caption ? [["figcaption", {}, caption]] : []),
    ];
  },
});
