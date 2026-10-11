import { useState } from "react";

/** Share addresses for a page. Everything user-controlled goes through encodeURIComponent. */
export function shareLinks(url, title) {
  const u = encodeURIComponent(url);
  const t = encodeURIComponent(title);
  return {
    x: `https://twitter.com/intent/tweet?url=${u}&text=${t}`,
    facebook: `https://www.facebook.com/sharer/sharer.php?u=${u}`,
  };
}

export default function ShareButtons({ url, title }) {
  const [message, setMessage] = useState("");
  const links = shareLinks(url, title);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(url);
      setMessage("Link copied.");
    } catch {
      setMessage("Could not copy. Select the address bar and copy it from there.");
    }
    setTimeout(() => setMessage(""), 3000);
  };

  return (
    <div className="share" role="group" aria-label="Share this story">
      <span className="share-label">Share</span>
      <button type="button" className="btn secondary small" onClick={copy}>Copy link</button>
      <a className="btn secondary small" href={links.x} target="_blank" rel="noopener noreferrer">Share on X</a>
      <a className="btn secondary small" href={links.facebook} target="_blank" rel="noopener noreferrer">Share on Facebook</a>
      <span className="share-status" role="status">{message}</span>
    </div>
  );
}
