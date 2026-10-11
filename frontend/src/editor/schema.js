// The ONLY place that knows how editor JSON and server JSON differ.
//
//  - The editor's image node carries extra display attrs (src, width, height) so it can show the picture.
//  - The server schema stores only assetId, alt, caption, align, size and rejects/ignores everything else.
//
// toServerDoc()   editor JSON -> what we send to the API (whitelists every node and mark attribute)
// fromServerDoc() API JSON    -> what we load into the editor (keeps src/width/height the server resolved)

const NODE_ATTRS = {
  paragraph: ["textAlign"],
  heading: ["level", "textAlign"],
  orderedList: ["start"],
  image: ["assetId", "alt", "caption", "align", "size"],
  youtube: ["videoId"],
};
const MARK_ATTRS = { link: ["href"] };

export const emptyDoc = () => ({ type: "doc", content: [{ type: "paragraph" }] });

const pick = (attrs, allowed) => {
  const out = {};
  allowed.forEach((key) => {
    if (attrs && attrs[key] !== undefined && attrs[key] !== null) out[key] = attrs[key];
  });
  return out;
};

function cleanMark(mark) {
  const attrs = pick(mark.attrs, MARK_ATTRS[mark.type] || []);
  return Object.keys(attrs).length ? { type: mark.type, attrs } : { type: mark.type };
}

function cleanNode(node) {
  const out = { type: node.type };
  const attrs = pick(node.attrs, NODE_ATTRS[node.type] || []);
  if (Object.keys(attrs).length) out.attrs = attrs;
  if (typeof node.text === "string") out.text = node.text;
  if (Array.isArray(node.marks) && node.marks.length) out.marks = node.marks.map(cleanMark);
  if (Array.isArray(node.content)) out.content = node.content.map(cleanNode);
  return out;
}

export function toServerDoc(json) {
  if (!json || json.type !== "doc") return emptyDoc();
  const doc = cleanNode(json);
  if (!doc.content || doc.content.length === 0) doc.content = [{ type: "paragraph" }];
  return doc;
}

// Defaults match the server's (center / full), so a node missing these attrs still behaves.
function loadNode(node) {
  const out = JSON.parse(JSON.stringify({ ...node, content: undefined }));
  if (node.type === "image") {
    out.attrs = { align: "center", size: "full", alt: "", caption: "", ...(node.attrs || {}) };
  }
  if (Array.isArray(node.content)) out.content = node.content.map(loadNode);
  return out;
}

export function fromServerDoc(json) {
  if (!json || json.type !== "doc") return emptyDoc();
  const doc = loadNode(json);
  if (!doc.content || doc.content.length === 0) doc.content = [{ type: "paragraph" }];
  return doc;
}
