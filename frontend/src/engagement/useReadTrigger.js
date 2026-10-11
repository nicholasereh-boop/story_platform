import { useEffect, useRef } from "react";

// Calls onReach() once when `sentinelRef` (an invisible marker placed ~60% down the story) comes into view.
// Uses IntersectionObserver, with a scroll listener as the fallback. It never fires before the reader has actually
// scrolled, so a short story that fits on the screen does not trigger it the moment the page loads.
// `resetKey` (e.g. the story slug) re-arms the trigger when the reader moves to another story.
export function useReadTrigger(sentinelRef, onReach, enabled = true, resetKey = null) {
  const callback = useRef(onReach);
  callback.current = onReach;

  useEffect(() => {
    const el = sentinelRef.current;
    if (!enabled || !el) return undefined;
    let fired = false;
    const cleanups = [];
    const fire = () => {
      if (fired) return;
      fired = true;
      cleanups.forEach((fn) => fn());
      callback.current();
    };
    const whenScrolled = () => {
      if (window.scrollY > 0) {
        fire();
      } else {
        window.addEventListener("scroll", fire, { once: true, passive: true });
        cleanups.push(() => window.removeEventListener("scroll", fire));
      }
    };

    if (typeof IntersectionObserver !== "undefined") {
      const observer = new IntersectionObserver((entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          observer.disconnect();
          whenScrolled();
        }
      });
      observer.observe(el);
      cleanups.push(() => observer.disconnect());
    } else {
      const onScroll = () => {
        if (el.getBoundingClientRect().top <= window.innerHeight) fire();
      };
      window.addEventListener("scroll", onScroll, { passive: true });
      cleanups.push(() => window.removeEventListener("scroll", onScroll));
    }
    return () => cleanups.forEach((fn) => fn());
  }, [sentinelRef, enabled, resetKey]);
}
