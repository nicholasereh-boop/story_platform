import { useState } from "react";
import Modal from "../Modal";
import MediaLibrary from "./MediaLibrary";

// Modal that lets the user choose (or upload then choose) an image. Calls onPick(asset) then closes.
// Used by the editor ("insert image") and by the story cover selector.
export default function MediaPicker({ title = "Choose an image", onPick, onClose }) {
  const [chosen, setChosen] = useState(null);
  return (
    <Modal title={title} onClose={onClose} wide>
      <MediaLibrary selectedId={chosen?.id} onSelect={setChosen} />
      <div className="row end sticky-foot">
        <button type="button" className="btn secondary" onClick={onClose}>Cancel</button>
        <button type="button" className="btn" disabled={!chosen} onClick={() => { onPick(chosen); onClose(); }}>
          Use this image
        </button>
      </div>
    </Modal>
  );
}
