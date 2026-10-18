import { useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { createCategory, listCategories } from "../api";

// Category checkboxes for the story editor, plus a small "add a category" box so the list is never a dead end.
// value: array of selected category ids. onChange(newIds): called when a box is ticked, cleared or a category is added.
export default function CategoryPicker({ value, onChange }) {
  const queryClient = useQueryClient();
  const categories = useQuery({ queryKey: ["categories"], queryFn: listCategories });
  const [name, setName] = useState("");
  const [addError, setAddError] = useState("");
  const valueRef = useRef(value); // always the latest ticks, even when a request finishes after the person ticked more boxes
  valueRef.current = value;

  const add = useMutation({
    mutationFn: (newName) => createCategory(newName),
    onSuccess: async (created) => {
      await queryClient.invalidateQueries({ queryKey: ["categories"] });
      const latest = valueRef.current;
      if (created?.id != null && !latest.includes(created.id)) onChange([...latest, created.id]); // tick the new one
      setName("");
      setAddError("");
    },
    onError: (err) => setAddError(err.fieldErrors?.name?.[0] || err.friendly || "Could not add the category."),
  });

  const toggle = (id) => onChange(value.includes(id) ? value.filter((x) => x !== id) : [...value, id]);

  const submitNew = () => {
    const clean = name.trim();
    if (!clean) {
      setAddError("Type a category name first.");
      return;
    }
    setAddError("");
    add.mutate(clean);
  };

  const list = Array.isArray(categories.data) ? categories.data : [];

  return (
    <div className="category-picker">
      {categories.isLoading && <p className="muted small">Loading…</p>}
      {categories.isError && (
        <p className="field-error" role="alert">
          {categories.error.friendly} <button type="button" className="link-button" onClick={() => categories.refetch()}>Try again</button>
        </p>
      )}
      {categories.isSuccess && list.length === 0 && <p className="muted small">No categories yet. Add the first one below.</p>}

      {list.length > 0 && (
        <ul className="category-list" aria-label="Categories">
          {list.map((c) => (
            <li key={c.id}>
              <label className="category-row">
                <input type="checkbox" checked={value.includes(c.id)} onChange={() => toggle(c.id)} />
                <span>{c.name}</span>
              </label>
            </li>
          ))}
        </ul>
      )}

      <div className="category-add">
        <label htmlFor="new-category" className="small">Add a category</label>
        <div className="row">
          <input
            id="new-category"
            type="text"
            maxLength={80}
            value={name}
            placeholder="e.g. Travel"
            onChange={(e) => { setName(e.target.value); setAddError(""); }}
            onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); submitNew(); } }}
          />
          <button type="button" className="btn secondary small" disabled={add.isPending} onClick={submitNew}>{add.isPending ? "Adding…" : "Add"}</button>
        </div>
        {addError && <p className="field-error" role="alert">{addError}</p>}
      </div>
    </div>
  );
}
