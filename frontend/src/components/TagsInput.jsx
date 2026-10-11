import { useEffect, useId, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { createTag, searchTags } from "../api";

// Tag chips + autocomplete. Enter picks the highlighted suggestion, or creates a new tag from the typed text.
// `value` is a list of {id, name}.
export default function TagsInput({ value, onChange, onError }) {
  const listId = useId();
  const [text, setText] = useState("");
  const [term, setTerm] = useState("");
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const t = setTimeout(() => setTerm(text.trim()), 200);
    return () => clearTimeout(t);
  }, [text]);

  const { data } = useQuery({ queryKey: ["tags", term], queryFn: () => searchTags(term), enabled: term.length > 0 });
  const chosen = new Set(value.map((t) => t.id));
  const suggestions = term ? (data || []).filter((t) => !chosen.has(t.id)).slice(0, 8) : [];

  const add = (tag) => {
    if (!chosen.has(tag.id)) onChange([...value, { id: tag.id, name: tag.name }]);
    setText(""); setTerm(""); setActive(-1); setOpen(false);
  };

  const commit = async () => {
    if (active >= 0 && suggestions[active]) return add(suggestions[active]);
    const name = text.trim();
    if (!name) return;
    const exact = (data || []).find((t) => t.name.toLowerCase() === name.toLowerCase());
    if (exact) return add(exact);
    setBusy(true);
    try {
      add(await createTag(name)); // create-on-enter
    } catch (err) {
      onError?.(err.fieldErrors?.name?.[0] || err.friendly);
    } finally {
      setBusy(false);
    }
  };

  const onKeyDown = (e) => {
    if (e.key === "Enter") { e.preventDefault(); commit(); }
    else if (e.key === "ArrowDown") { e.preventDefault(); setOpen(true); setActive((i) => Math.min(i + 1, suggestions.length - 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActive((i) => Math.max(i - 1, -1)); }
    else if (e.key === "Escape") setOpen(false);
    else if (e.key === "Backspace" && !text && value.length) onChange(value.slice(0, -1));
  };

  return (
    <div className="tags-input">
      {value.length > 0 && (
        <ul className="chips">
          {value.map((t) => (
            <li key={t.id} className="chip">
              {t.name}
              <button type="button" aria-label={`Remove tag ${t.name}`} onClick={() => onChange(value.filter((x) => x.id !== t.id))}>✕</button>
            </li>
          ))}
        </ul>
      )}
      <input
        type="text"
        role="combobox"
        aria-label="Add a tag"
        aria-expanded={open && suggestions.length > 0}
        aria-controls={listId}
        aria-autocomplete="list"
        aria-activedescendant={active >= 0 ? `${listId}-${active}` : undefined}
        placeholder="Type a tag and press Enter"
        value={text}
        disabled={busy}
        onChange={(e) => { setText(e.target.value); setOpen(true); setActive(-1); }}
        onKeyDown={onKeyDown}
        onBlur={() => setTimeout(() => setOpen(false), 120)}
      />
      {open && suggestions.length > 0 && (
        <ul id={listId} role="listbox" className="suggest">
          {suggestions.map((t, i) => (
            <li key={t.id} id={`${listId}-${i}`} role="option" aria-selected={i === active} className={i === active ? "on" : undefined} onMouseDown={(e) => { e.preventDefault(); add(t); }}>
              {t.name}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
