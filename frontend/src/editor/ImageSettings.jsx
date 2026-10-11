// Panel shown while an image is selected in the editor: alt text, caption, alignment, size, remove.
// Edits are applied immediately as node attribute updates (no focus change, so typing is not interrupted).
const ALIGNS = [["left", "Left"], ["center", "Center"], ["right", "Right"]];
const SIZES = [["small", "Small"], ["medium", "Medium"], ["full", "Full width"]];

export default function ImageSettings({ editor }) {
  if (!editor || !editor.isActive("image")) return null;
  const attrs = editor.getAttributes("image");
  const set = (patch) => editor.chain().updateAttributes("image", patch).run();

  return (
    <section className="image-settings" aria-label="Image settings">
      <h3>Image settings</h3>
      <div className="grid-2">
        <div className="field">
          <label htmlFor="img-alt">Alt text</label>
          <input id="img-alt" maxLength={300} value={attrs.alt || ""} onChange={(e) => set({ alt: e.target.value })} />
          <p className="hint">Describe what the picture shows, in a short sentence, for people who cannot see it.</p>
          {!attrs.alt && <p className="warn" role="status">⚠ No alt text. Screen-reader users will not know what this image shows.</p>}
        </div>
        <div className="field">
          <label htmlFor="img-caption">Caption</label>
          <input id="img-caption" maxLength={500} value={attrs.caption || ""} onChange={(e) => set({ caption: e.target.value })} />
        </div>
        <div className="field">
          <label htmlFor="img-align">Alignment</label>
          <select id="img-align" value={attrs.align} onChange={(e) => set({ align: e.target.value })}>
            {ALIGNS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </div>
        <div className="field">
          <label htmlFor="img-size">Size</label>
          <select id="img-size" value={attrs.size} onChange={(e) => set({ size: e.target.value })}>
            {SIZES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
        </div>
      </div>
      <button type="button" className="btn danger small" onClick={() => editor.chain().focus().deleteSelection().run()}>Remove image</button>
    </section>
  );
}
