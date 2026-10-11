import { Node } from "@tiptap/core";
import { extractYoutubeId, youtubeEmbedUrl } from "../utils/youtube";

// Custom "youtube" node. The ONLY attribute is the 11-character videoId. The iframe is generated here from that id;
// a user-supplied iframe/URL is never stored or rendered.
export const YoutubeNode = Node.create({
  name: "youtube",
  group: "block",
  atom: true,
  draggable: true,

  addAttributes() {
    return {
      videoId: { default: null, parseHTML: (el) => extractYoutubeId(el.getAttribute("data-youtube-id")) },
    };
  },

  parseHTML() {
    return [
      {
        tag: "div[data-youtube-id]",
        getAttrs: (el) => (extractYoutubeId(el.getAttribute("data-youtube-id")) ? null : false), // bad id -> ignore
      },
    ];
  },

  renderHTML({ node }) {
    const id = extractYoutubeId(node.attrs.videoId);
    if (!id) return ["div", { class: "yt-embed yt-invalid" }, "Invalid video"];
    return [
      "div",
      { class: "yt-embed", "data-youtube-id": id },
      ["iframe", { src: youtubeEmbedUrl(id), title: "YouTube video", loading: "lazy", allowfullscreen: "true", referrerpolicy: "strict-origin-when-cross-origin" }],
    ];
  },
});
