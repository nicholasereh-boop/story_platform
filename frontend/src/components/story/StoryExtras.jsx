import { useEffect, useRef, useState } from "react";

// A thin rainbow bar at the very top that fills as you read down the page, plus a round "back to top" button that
// appears once you have scrolled a bit. Both only exist on the story page.
export default function StoryExtras() {
  const bar = useRef(null);
  const [showTop, setShowTop] = useState(false);

  useEffect(() => {
    let frame = 0;
    const update = () => {
      frame = 0;
      const doc = document.documentElement;
      const max = Math.max(1, doc.scrollHeight - window.innerHeight);
      const progress = Math.min(1, Math.max(0, window.scrollY / max));
      bar.current?.style.setProperty("--p", String(progress));
      setShowTop(window.scrollY > 600);
    };
    const onScroll = () => { if (!frame) frame = window.requestAnimationFrame(update); };
    update();
    window.addEventListener("scroll", onScroll, { passive: true });
    window.addEventListener("resize", onScroll);
    return () => {
      window.removeEventListener("scroll", onScroll);
      window.removeEventListener("resize", onScroll);
      if (frame) window.cancelAnimationFrame(frame);
    };
  }, []);

  return (
    <>
      <div className="sp-progress" ref={bar} role="progressbar" aria-label="Reading progress" aria-hidden="true"><span /></div>
      <button
        type="button"
        className={`sp-top${showTop ? " is-visible" : ""}`}
        aria-label="Back to the top"
        tabIndex={showTop ? 0 : -1}
        onClick={() => window.scrollTo?.({ top: 0, behavior: "smooth" })}
      >
        <span aria-hidden="true">↑</span>
      </button>
    </>
  );
}