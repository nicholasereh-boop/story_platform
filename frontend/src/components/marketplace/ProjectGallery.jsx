import { useCallback, useEffect, useRef, useState } from "react";
import { safeImageSrc } from "./shared";

// Screenshots change by themselves every 3 seconds. The slideshow waits while the reader is using it (mouse over it,
// keyboard focus inside it, a hidden browser tab) and can be paused with the button. People who ask their device for
// less motion start paused and can press Play. Swipe, the arrows, the dots and the arrow keys all work too.
const INTERVAL_MS = 3000;

function reducedMotion() {
  return typeof window !== "undefined" && typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export default function ProjectGallery({ screenshots = [], title }) {
  const shots = screenshots.filter((s) => safeImageSrc(s.url));
  const count = shots.length;
  const [index, setIndex] = useState(0);
  const [userPaused, setUserPaused] = useState(reducedMotion);
  const [hovering, setHovering] = useState(false);
  const [focused, setFocused] = useState(false);
  const [tabVisible, setTabVisible] = useState(true);
  const touchStart = useRef(null);

  const active = count === 0 ? 0 : Math.min(index, count - 1);
  const playing = count > 1 && !userPaused && !hovering && !focused && tabVisible;

  const go = useCallback((i) => setIndex(((i % count) + count) % count), [count]);

  // The 3-second timer restarts after every change, so a manual click always gets a full 3 seconds on screen.
  useEffect(() => {
    if (!playing) return undefined;
    const id = setTimeout(() => setIndex((Math.min(active, count - 1) + 1) % count), INTERVAL_MS);
    return () => clearTimeout(id);
  }, [playing, active, count]);

  useEffect(() => {
    const onVisibility = () => setTabVisible(document.visibilityState !== "hidden");
    document.addEventListener("visibilitychange", onVisibility);
    return () => document.removeEventListener("visibilitychange", onVisibility);
  }, []);

  if (count === 0) return null;

  const onKeyDown = (e) => {
    if (count < 2) return;
    if (e.key === "ArrowRight") { e.preventDefault(); go(active + 1); }
    if (e.key === "ArrowLeft") { e.preventDefault(); go(active - 1); }
  };
  const onTouchEnd = (e) => {
    const start = touchStart.current;
    touchStart.current = null;
    if (start === null || count < 2) return;
    const dx = (e.changedTouches?.[0]?.clientX ?? start) - start;
    if (Math.abs(dx) > 40) go(active + (dx < 0 ? 1 : -1));
  };
  const keyboardFocus = (e) => {
    try { return e.target.matches(":focus-visible"); } catch { return true; }
  };

  return (
    <section
      aria-label="Screenshots"
      aria-roledescription="carousel"
      className="mp-gallery"
      onKeyDown={onKeyDown}
      onPointerEnter={(e) => { if (e.pointerType !== "touch") setHovering(true); }}
      onPointerLeave={(e) => { if (e.pointerType !== "touch") setHovering(false); }}
      onFocus={(e) => { if (keyboardFocus(e)) setFocused(true); }}
      onBlur={() => setFocused(false)}
      onTouchStart={(e) => { touchStart.current = e.touches?.[0]?.clientX ?? null; }}
      onTouchEnd={onTouchEnd}
    >
      <div className="mp-gallery-main" aria-live={playing ? "off" : "polite"}>
        {shots.map((s, i) => (
          <figure key={s.id} className={`mp-slide${i === active ? " is-active" : ""}`} aria-hidden={i === active ? undefined : "true"}>
            <img
              src={safeImageSrc(s.url)}
              alt={s.alt_text || `Screenshot ${i + 1} of ${title}`}
              width={s.width || undefined}
              height={s.height || undefined}
              loading={i === 0 ? "eager" : "lazy"}
              draggable="false"
            />
          </figure>
        ))}

        {count > 1 && (
          <>
            <button type="button" className="mp-nav prev" aria-label="Previous screenshot" onClick={() => go(active - 1)}><span aria-hidden="true">‹</span></button>
            <button type="button" className="mp-nav next" aria-label="Next screenshot" onClick={() => go(active + 1)}><span aria-hidden="true">›</span></button>
            <div className="mp-gallery-tools">
              <span className="mp-counter" aria-hidden="true">{active + 1} / {count}</span>
              <button type="button" className="mp-playpause" onClick={() => setUserPaused((p) => !p)} aria-label={userPaused ? "Play slideshow" : "Pause slideshow"}>
                <span aria-hidden="true">{userPaused ? "▶" : "❚❚"}</span>
              </button>
            </div>
            {playing && <span key={active} className="mp-gallery-progress" style={{ animationDuration: `${INTERVAL_MS}ms` }} aria-hidden="true" />}
          </>
        )}
      </div>

      {count > 1 && (
        <div className="mp-thumbs">
          {shots.map((s, i) => (
            <button key={s.id} type="button" aria-label={`Show screenshot ${i + 1} of ${count}`} aria-current={i === active ? "true" : undefined} onClick={() => go(i)}>
              <img src={safeImageSrc(s.url)} alt="" loading="lazy" draggable="false" />
            </button>
          ))}
        </div>
      )}
    </section>
  );
}