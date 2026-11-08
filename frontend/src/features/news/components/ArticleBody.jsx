import { createElement } from "react";

// Renders the server's already-sanitised article HTML as React elements, WITHOUT innerHTML: the markup is parsed with DOMParser
// into an inert document and rebuilt node by node from an allowlist. Anything unknown is dropped (its text is kept), attributes
// are never copied except a safe link address, and links always open safely. Defence in depth: the server sanitises first.
const TAGS = new Set(["p", "br", "h2", "h3", "h4", "ul", "ol", "li", "blockquote", "strong", "em", "b", "i", "u", "a", "hr", "code", "pre"]);
const VOID = new Set(["br", "hr"]);
const SAFE_LINK = /^(https?:|mailto:)/i;

export function toNodes(html) {
  if (!html || typeof DOMParser === "undefined") return [];
  const doc = new DOMParser().parseFromString(`<!doctype html><body>${html}`, "text/html");
  let key = 0;
  const build = (node) => {
    if (node.nodeType === 3) return node.nodeValue;
    if (node.nodeType !== 1) return null;
    const tag = node.nodeName.toLowerCase();
    const kids = Array.from(node.childNodes).map(build).filter((n) => n !== null && n !== "");
    if (!TAGS.has(tag)) return kids.length ? kids : null; // unknown tag: keep its text, lose the tag
    const props = { key: key++ };
    if (tag === "a") {
      const href = (node.getAttribute("href") || "").trim();
      if (!SAFE_LINK.test(href)) return kids.length ? kids : null;
      Object.assign(props, { href, rel: "nofollow noopener noreferrer", target: "_blank" });
    }
    return VOID.has(tag) ? createElement(tag, props) : createElement(tag, props, ...kids);
  };
  return Array.from(doc.body.childNodes).map(build).filter((n) => n !== null);
}

export default function ArticleBody({ html }) {
  return <div className="nw-body">{toNodes(html)}</div>;
}
