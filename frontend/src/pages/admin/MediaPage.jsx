import { useState } from "react";
import MediaLibrary from "../../components/media/MediaLibrary";
import MediaPanel from "../../components/media/MediaPanel";

export default function MediaPage() {
  const [selected, setSelected] = useState(null);
  return (
    <>
      <h1>Media</h1>
      <div className={`media-page${selected ? " with-panel" : ""}`}>
        <MediaLibrary selectedId={selected?.id} onSelect={setSelected} />
        {selected && <MediaPanel key={selected.id} assetId={selected.id} onClose={() => setSelected(null)} />}
      </div>
    </>
  );
}
