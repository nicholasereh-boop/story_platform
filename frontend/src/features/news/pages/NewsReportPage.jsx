import { useState } from "react";
import { Link } from "react-router-dom";
import { useDocumentMeta } from "../../../hooks/useDocumentMeta";
import { submitNewsComplaint } from "../api/news";
import { useNewsConfig } from "../hooks/useNewsConfig";
import { errorText } from "../utils/text";
import "../news.css";

// The public copyright / accuracy complaint form. The answer is the same whether or not the article was found.
export default function NewsReportPage() {
  useDocumentMeta({ title: "Report a problem — News", robots: "noindex" });
  const config = useNewsConfig();
  const [form, setForm] = useState({ name: "", email: "", article: "", claim: "copyright", message: "" });
  const [state, setState] = useState({ busy: false, done: false, error: "" });
  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }));
  const submit = async (e) => {
    e.preventDefault();
    setState({ busy: true, done: false, error: "" });
    try {
      await submitNewsComplaint(form);
      setState({ busy: false, done: true, error: "" });
    } catch (err) {
      setState({ busy: false, done: false, error: errorText(err) });
    }
  };
  if (state.done) {
    return (
      <div className="nw-page">
        <h1 className="nw-h1">Thank you</h1>
        <p className="nw-lede" role="status">We have received your report. An editor will review it and, if it is credible, the article is taken down while we look into it.</p>
        <p><Link to="/news">← Back to the news</Link></p>
      </div>
    );
  }
  return (
    <div className="nw-page nw-narrow">
      <h1 className="nw-h1">Report a problem with an article</h1>
      <p className="nw-lede">Use this form for copyright or accuracy concerns.{config.copyright_contact && <> You can also write to <a href={`mailto:${config.copyright_contact}`}>{config.copyright_contact}</a>.</>}</p>
      <form className="nw-form" onSubmit={submit}>
        <label>Your name<input required maxLength={120} value={form.name} onChange={set("name")} autoComplete="name" /></label>
        <label>Your email<input type="email" required value={form.email} onChange={set("email")} autoComplete="email" /></label>
        <label>Link to the article<input value={form.article} onChange={set("article")} placeholder="https://…/news/article-name" /></label>
        <label>What is the problem?
          <select value={form.claim} onChange={set("claim")}>
            <option value="copyright">Copyright</option><option value="accuracy">Accuracy</option><option value="other">Something else</option>
          </select>
        </label>
        <label>Details<textarea required minLength={10} maxLength={4000} rows={6} value={form.message} onChange={set("message")} /></label>
        {state.error && <p className="nw-error" role="alert">{state.error}</p>}
        <button type="submit" className="btn" disabled={state.busy}>{state.busy ? "Sending…" : "Send report"}</button>
      </form>
    </div>
  );
}
