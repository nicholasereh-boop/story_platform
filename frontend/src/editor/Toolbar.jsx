import { useRef } from "react";

// One toolbar button: aria-label + title (tooltip) + aria-pressed state.
function Btn({ label, shortcut, active = false, disabled = false, onClick, children }) {
  const title = shortcut ? `${label} (${shortcut})` : label;
  return (
    <button type="button" className={`tb-btn${active ? " on" : ""}`} aria-label={label} title={title} aria-pressed={active} disabled={disabled} onClick={onClick}>
      {children}
    </button>
  );
}

const Group = ({ label, children }) => <div className="tb-group" role="group" aria-label={label}>{children}</div>;

export default function Toolbar({ editor, onLink, onImage, onYoutube }) {
  const ref = useRef(null);
  if (!editor) return null;
  const run = (fn) => () => fn(editor.chain().focus()).run();
  const heading = [1, 2, 3, 4, 5, 6].find((level) => editor.isActive("heading", { level }));

  // Left/Right arrows move between buttons (toolbar pattern); Tab still works normally.
  const onKeyDown = (event) => {
    if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
    if (event.target.tagName === "SELECT") return;
    const items = Array.from(ref.current.querySelectorAll("button:not([disabled]), select"));
    const i = items.indexOf(document.activeElement);
    if (i === -1) return;
    event.preventDefault();
    items[(i + (event.key === "ArrowRight" ? 1 : -1) + items.length) % items.length].focus();
  };

  const setStyle = (value) => {
    const chain = editor.chain().focus();
    if (value === "p") chain.setParagraph().run();
    else chain.setHeading({ level: Number(value) }).run();
  };

  return (
    <div ref={ref} className="toolbar" role="toolbar" aria-label="Formatting" onKeyDown={onKeyDown}>
      <Group label="Text style">
        <select aria-label="Text style" title="Text style" value={heading ? String(heading) : "p"} onChange={(e) => setStyle(e.target.value)}>
          <option value="p">Paragraph</option>
          {[1, 2, 3, 4, 5, 6].map((l) => <option key={l} value={l}>Heading {l}</option>)}
        </select>
      </Group>
      <Group label="Text formatting">
        <Btn label="Bold" shortcut="Ctrl+B" active={editor.isActive("bold")} onClick={run((c) => c.toggleBold())}><b>B</b></Btn>
        <Btn label="Italic" shortcut="Ctrl+I" active={editor.isActive("italic")} onClick={run((c) => c.toggleItalic())}><i>I</i></Btn>
        <Btn label="Underline" shortcut="Ctrl+U" active={editor.isActive("underline")} onClick={run((c) => c.toggleUnderline())}><u>U</u></Btn>
        <Btn label="Strikethrough" active={editor.isActive("strike")} onClick={run((c) => c.toggleStrike())}><s>S</s></Btn>
        <Btn label="Link" shortcut="Ctrl+K" active={editor.isActive("link")} onClick={onLink}>🔗</Btn>
      </Group>
      <Group label="Blocks">
        <Btn label="Bulleted list" active={editor.isActive("bulletList")} onClick={run((c) => c.toggleBulletList())}>• List</Btn>
        <Btn label="Numbered list" active={editor.isActive("orderedList")} onClick={run((c) => c.toggleOrderedList())}>1. List</Btn>
        <Btn label="Quote" active={editor.isActive("blockquote")} onClick={run((c) => c.toggleBlockquote())}>❝</Btn>
        <Btn label="Horizontal rule" onClick={run((c) => c.setHorizontalRule())}>―</Btn>
      </Group>
      <Group label="Alignment">
        <Btn label="Align left" active={editor.isActive({ textAlign: "left" })} onClick={run((c) => c.setTextAlign("left"))}>⇤</Btn>
        <Btn label="Align center" active={editor.isActive({ textAlign: "center" })} onClick={run((c) => c.setTextAlign("center"))}>↔</Btn>
        <Btn label="Align right" active={editor.isActive({ textAlign: "right" })} onClick={run((c) => c.setTextAlign("right"))}>⇥</Btn>
        <Btn label="Justify" active={editor.isActive({ textAlign: "justify" })} onClick={run((c) => c.setTextAlign("justify"))}>☰</Btn>
      </Group>
      <Group label="Media">
        <Btn label="Insert image" onClick={onImage}>🖼</Btn>
        <Btn label="Insert YouTube video" onClick={onYoutube}>▶</Btn>
      </Group>
      <Group label="History">
        <Btn label="Undo" shortcut="Ctrl+Z" disabled={!editor.can().undo()} onClick={run((c) => c.undo())}>↶</Btn>
        <Btn label="Redo" shortcut="Ctrl+Shift+Z" disabled={!editor.can().redo()} onClick={run((c) => c.redo())}>↷</Btn>
      </Group>
    </div>
  );
}
