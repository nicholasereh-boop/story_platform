import { useRef, useState } from "react";
import { EditorContent, useEditor } from "@tiptap/react";
import MediaPicker from "../components/media/MediaPicker";
import { buildExtensions } from "./extensions";
import { toServerDoc } from "./schema";
import Toolbar from "./Toolbar";
import ImageSettings from "./ImageSettings";
import LinkDialog from "./LinkDialog";
import YoutubeDialog from "./YoutubeDialog";
import { textStats } from "../utils/stats";

// The rich-text editor. It takes a document in the SERVER schema (use fromServerDoc first) and reports every
// change as a server-schema document (already passed through toServerDoc), so the parent never sees editor internals.
//
//   initialContent  doc to load (read once, remount with a new `key` to load a different document)
//   onChange(doc)   called after every edit
//   onReady(doc)    called once with the editor-normalised version of initialContent (the baseline for "dirty")
//   error           server message about the content, shown above the editor
export default function StoryEditor({ initialContent, onChange, onReady, error }) {
  const [dialog, setDialog] = useState(null); // null | "link" | "youtube" | "image"

  // Editor callbacks are captured once, so they go through refs to always call the latest props.
  const onChangeRef = useRef(onChange);
  const onReadyRef = useRef(onReady);
  onChangeRef.current = onChange;
  onReadyRef.current = onReady;

  const editor = useEditor({
    extensions: buildExtensions({ onLinkShortcut: () => setDialog("link") }),
    content: initialContent,
    editorProps: {
      attributes: { class: "editor-surface prose", role: "textbox", "aria-multiline": "true", "aria-label": "Story content" },
    },
    onCreate: ({ editor: ed }) => onReadyRef.current?.(toServerDoc(ed.getJSON())),
    onUpdate: ({ editor: ed }) => onChangeRef.current?.(toServerDoc(ed.getJSON())),
  });

  const stats = textStats(editor ? editor.getText({ blockSeparator: " " }) : "");

  const applyLink = (href) => {
    const chain = editor.chain().focus();
    if (editor.isActive("link") || !editor.state.selection.empty) {
      chain.extendMarkRange("link").setLink({ href }).run();
    } else {
      // nothing selected: insert the address itself as the link text
      chain.insertContent({ type: "text", text: href, marks: [{ type: "link", attrs: { href } }] }).run();
    }
  };

  const insertImage = (asset) =>
    editor
      .chain()
      .focus()
      .insertContent({
        type: "image",
        attrs: {
          assetId: asset.id,
          alt: asset.alt_text || "",
          caption: asset.caption || "",
          align: "center",
          size: "full",
          src: asset.url,
          width: asset.width,
          height: asset.height,
        },
      })
      .run();

  const insertYoutube = (videoId) => editor.chain().focus().insertContent({ type: "youtube", attrs: { videoId } }).run();

  return (
    <div className="editor">
      <Toolbar editor={editor} onLink={() => setDialog("link")} onImage={() => setDialog("image")} onYoutube={() => setDialog("youtube")} />
      {error && <div className="notice error" role="alert">{error}</div>}
      <ImageSettings editor={editor} />
      <EditorContent editor={editor} />
      <div className="statusbar" aria-live="off">
        <span>{stats.words} {stats.words === 1 ? "word" : "words"}</span>
        <span>{stats.characters} characters</span>
        <span>{stats.readingMinutes === 0 ? "Reading time: —" : `${stats.readingMinutes} min read`}</span>
      </div>

      {dialog === "link" && editor && (
        <LinkDialog
          initialHref={editor.getAttributes("link").href || ""}
          hasLink={editor.isActive("link")}
          onApply={applyLink}
          onRemove={() => editor.chain().focus().extendMarkRange("link").unsetLink().run()}
          onClose={() => setDialog(null)}
        />
      )}
      {dialog === "youtube" && <YoutubeDialog onInsert={insertYoutube} onClose={() => setDialog(null)} />}
      {dialog === "image" && <MediaPicker title="Insert image" onPick={insertImage} onClose={() => setDialog(null)} />}
    </div>
  );
}
