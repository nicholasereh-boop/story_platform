import { Extension } from "@tiptap/core";
import StarterKit from "@tiptap/starter-kit";
import Underline from "@tiptap/extension-underline";
import Link from "@tiptap/extension-link";
import TextAlign from "@tiptap/extension-text-align";
import Placeholder from "@tiptap/extension-placeholder";
import { ImageNode } from "./ImageNode";
import { YoutubeNode } from "./YoutubeNode";
import { isSafeHref } from "../utils/links";

// The extension list IS the schema. Anything not loaded here cannot be typed, pasted or produced by a shortcut:
// codeBlock and code are switched off, there is no table, no raw HTML, no stock image/iframe node.

// Link: only http/https/mailto. Pasted <a href="javascript:..."> is not turned into a link at all.
const SafeLink = Link.extend({
  parseHTML() {
    return [{ tag: "a[href]", getAttrs: (el) => (isSafeHref(el.getAttribute("href")) ? null : false) }];
  },
});

export function buildExtensions({ onLinkShortcut } = {}) {
  // Ctrl/Cmd+K opens the link dialog (bold, italic, underline and undo shortcuts come with their extensions).
  const LinkShortcut = Extension.create({
    name: "linkShortcut",
    addKeyboardShortcuts() {
      return {
        "Mod-k": () => {
          onLinkShortcut?.();
          return true;
        },
      };
    },
  });

  return [
    StarterKit.configure({
      heading: { levels: [1, 2, 3, 4, 5, 6] },
      codeBlock: false,
      code: false,
    }),
    Underline,
    SafeLink.configure({
      openOnClick: false,
      autolink: false,
      protocols: ["mailto"], // http and https are always allowed
      HTMLAttributes: { rel: "noopener noreferrer nofollow", target: "_blank" },
    }),
    TextAlign.configure({ types: ["heading", "paragraph"], alignments: ["left", "center", "right", "justify"] }),
    Placeholder.configure({ placeholder: "Start writing your story…" }),
    ImageNode,
    YoutubeNode,
    LinkShortcut,
  ];
}
