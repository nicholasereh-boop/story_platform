import { createElement } from "react";
import { isSafeHref } from "../utils/links";
import { extractYoutubeId, youtubeEmbedUrl } from "../utils/youtube";

// Renders story JSON (the server schema) as React elements.
//
// SAFETY: there is no raw-HTML injection anywhere. Every node type is handled explicitly in the switch
// below; a node type we do not know renders NOTHING (including its children). Text is rendered as React text, so
// it is always escaped. Phase 7 (public site) reuses this component unchanged.

const ALIGNS = ["left", "center", "right", "justify"];
const IMAGE_ALIGNS = ["left", "center", "right"];
const IMAGE_SIZES = ["small", "medium", "full"];

// Only our own media (relative URLs) or absolute http(s) addresses (object storage / CDN) may be image sources.
const isSafeSrc = (src) => typeof src === "string" && (/^\/(?!\/)/.test(src) || /^https?:\/\//i.test(src));

function applyMarks(text, marks = [], key) {
  let out = text;
  marks.forEach((mark, i) => {
    const k = `${key}-m${i}`;
    switch (mark.type) {
      case "bold": out = <strong key={k}>{out}</strong>; break;
      case "italic": out = <em key={k}>{out}</em>; break;
      case "underline": out = <u key={k}>{out}</u>; break;
      case "strike": out = <s key={k}>{out}</s>; break;
      case "link": {
        const href = mark.attrs?.href;
        // An unsafe link (e.g. javascript:) is dropped, the words stay.
        if (isSafeHref(href)) {
          out = (
            <a key={k} href={href} target="_blank" rel="noopener noreferrer nofollow">
              {out}
            </a>
          );
        }
        break;
      }
      default: break; // unknown mark: ignored
    }
  });
  return out;
}

function renderChildren(node, key) {
  return (node.content || []).map((child, i) => renderNode(child, `${key}.${i}`));
}

const alignClass = (node) => {
  const a = node.attrs?.textAlign;
  return ALIGNS.includes(a) && a !== "left" ? `ta-${a}` : undefined;
};

function renderNode(node, key) {
  if (!node || typeof node !== "object") return null;
  switch (node.type) {
    case "text":
      return typeof node.text === "string" ? <span key={key}>{applyMarks(node.text, node.marks, key)}</span> : null;
    case "paragraph":
      return <p key={key} className={alignClass(node)}>{renderChildren(node, key)}</p>;
    case "heading": {
      const level = Math.min(6, Math.max(1, Number(node.attrs?.level) || 2));
      return createElement(`h${level}`, { key, className: alignClass(node) }, renderChildren(node, key));
    }
    case "hardBreak":
      return <br key={key} />;
    case "horizontalRule":
      return <hr key={key} />;
    case "blockquote":
      return <blockquote key={key}>{renderChildren(node, key)}</blockquote>;
    case "bulletList":
      return <ul key={key}>{renderChildren(node, key)}</ul>;
    case "orderedList": {
      const start = Number(node.attrs?.start);
      return <ol key={key} start={Number.isInteger(start) && start > 1 ? start : undefined}>{renderChildren(node, key)}</ol>;
    }
    case "listItem":
      return <li key={key}>{renderChildren(node, key)}</li>;
    case "image": {
      const { src, alt = "", caption = "", width, height } = node.attrs || {};
      if (!isSafeSrc(src)) return null;
      const align = IMAGE_ALIGNS.includes(node.attrs?.align) ? node.attrs.align : "center";
      const size = IMAGE_SIZES.includes(node.attrs?.size) ? node.attrs.size : "full";
      return (
        <figure key={key} className={`story-image img-${align} img-${size}`}>
          <img src={src} alt={alt} width={width || undefined} height={height || undefined} loading="lazy" />
          {caption ? <figcaption>{caption}</figcaption> : null}
        </figure>
      );
    }
    case "youtube": {
      const id = extractYoutubeId(node.attrs?.videoId);
      if (!id) return null;
      return (
        <div key={key} className="yt-embed">
          <iframe
            src={youtubeEmbedUrl(id)}
            title="YouTube video"
            loading="lazy"
            allow="accelerometer; encrypted-media; gyroscope; picture-in-picture"
            allowFullScreen
            referrerPolicy="strict-origin-when-cross-origin"
          />
        </div>
      );
    }
    default:
      return null; // unknown node: renders nothing
  }
}

export default function StoryRenderer({ content }) {
  const nodes = content && content.type === "doc" && Array.isArray(content.content) ? content.content : [];
  return <div className="prose">{nodes.map((node, i) => renderNode(node, String(i)))}</div>;
}
