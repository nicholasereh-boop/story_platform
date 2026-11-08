import { describe, expect, it, vi } from "vitest";
import { createCoordinator } from "../player/VideoPlaybackCoordinator";
import { youtubeEmbedUrl } from "../utils/youtube";

// A stand-in for BroadcastChannel: every channel with the same name delivers to the OTHERS, like the real thing.
function makeBus() {
  const channels = new Set();
  const factory = () => {
    const channel = {
      onmessage: null,
      closed: false,
      postMessage(data) { for (const other of channels) if (other !== channel && !other.closed) other.onmessage?.({ data }); },
      close() { channel.closed = true; channels.delete(channel); },
    };
    channels.add(channel);
    return channel;
  };
  return { factory, open: () => channels.size };
}
const player = () => ({ pause: vi.fn() });
// A clock that moves forward on every reading, so two starts never share a millisecond unless a test wants them to.
const ticking = () => { let t = 1000; return () => ++t; };

describe("VideoPlaybackCoordinator (one tab)", () => {
  it("pauses every other player when one starts, and never the one that started", () => {
    const c = createCoordinator({ channelFactory: () => null });
    const a = player(); const b = player(); const d = player();
    c.register("a", a); c.register("b", b); c.register("d", d);
    expect(c.notifyPlaying("b")).toBe(true);
    expect(a.pause).toHaveBeenCalledTimes(1);
    expect(d.pause).toHaveBeenCalledTimes(1);
    expect(b.pause).not.toHaveBeenCalled();
    expect(c.getActiveId()).toBe("b");
    c.notifyPlaying("a"); // the newest start wins
    expect(b.pause).toHaveBeenCalledTimes(1);
    expect(c.getActiveId()).toBe("a");
  });

  it("stops talking to a player once it unregisters, and forgets it was active", () => {
    const c = createCoordinator({ channelFactory: () => null });
    const a = player(); const b = player();
    const stopA = c.register("a", a); c.register("b", b);
    c.notifyPlaying("a");
    stopA();
    expect(c.getActiveId()).toBeNull();
    c.notifyPlaying("b");
    expect(a.pause).not.toHaveBeenCalled();
    expect(c.playerCount()).toBe(1);
  });

  it("ignores a play report from a player that is not registered", () => {
    const c = createCoordinator({ channelFactory: () => null });
    const a = player();
    c.register("a", a);
    expect(c.notifyPlaying("ghost")).toBe(false);
    expect(a.pause).not.toHaveBeenCalled();
  });

  it("lets a stale unregister leave a newer player with the same id alone", () => {
    const c = createCoordinator({ channelFactory: () => null });
    const oldStop = c.register("x", player());
    const fresh = player(); const other = player();
    c.register("x", fresh); c.register("y", other);
    oldStop();
    expect(c.playerCount()).toBe(2);
    c.notifyPlaying("y");
    expect(fresh.pause).toHaveBeenCalledTimes(1);
  });

  it("keeps going when one player's pause() throws", () => {
    const c = createCoordinator({ channelFactory: () => null });
    const broken = { pause: () => { throw new Error("player is gone"); } };
    const ok = player();
    c.register("broken", broken); c.register("ok", ok); c.register("me", player());
    expect(() => c.notifyPlaying("me")).not.toThrow();
    expect(ok.pause).toHaveBeenCalledTimes(1);
  });

  it("marks a player as no longer active when it pauses or ends", () => {
    const c = createCoordinator({ channelFactory: () => null });
    c.register("a", player());
    c.notifyPlaying("a");
    c.notifyStopped("a");
    expect(c.getActiveId()).toBeNull();
  });

  it("gives out unique ids", () => {
    const c = createCoordinator({ channelFactory: () => null });
    expect(new Set([c.createId("story"), c.createId("story"), c.createId("lesson")]).size).toBe(3);
  });

  it("works when the browser has no BroadcastChannel or the channel cannot be created", () => {
    const c = createCoordinator({ channelFactory: () => { throw new Error("blocked"); } });
    const a = player(); const b = player();
    c.register("a", a); c.register("b", b);
    expect(() => c.notifyPlaying("b")).not.toThrow();
    expect(a.pause).toHaveBeenCalledTimes(1);
  });
});

describe("VideoPlaybackCoordinator (several tabs)", () => {
  it("pauses the other tab's players when a video starts here", () => {
    const bus = makeBus();
    const now = ticking();
    const tab1 = createCoordinator({ channelFactory: bus.factory, tabId: "t1", now });
    const tab2 = createCoordinator({ channelFactory: bus.factory, tabId: "t2", now });
    const story = player(); const lesson = player();
    tab1.register("story", story); tab2.register("lesson", lesson);
    tab2.notifyPlaying("lesson");
    expect(story.pause).toHaveBeenCalledTimes(1);
    expect(lesson.pause).not.toHaveBeenCalled();
    tab1.notifyPlaying("story"); // and back again
    expect(lesson.pause).toHaveBeenCalledTimes(1);
  });

  it("never broadcasts a pause, so a pause caused by the coordinator cannot bounce back", () => {
    const bus = makeBus();
    const now = ticking();
    const tab1 = createCoordinator({ channelFactory: bus.factory, tabId: "t1", now });
    const tab2 = createCoordinator({ channelFactory: bus.factory, tabId: "t2", now });
    const a = player(); const b = player();
    tab1.register("a", a); tab2.register("b", b);
    tab1.notifyPlaying("a");
    tab1.notifyStopped("a"); tab2.notifyStopped("b");
    expect(a.pause).not.toHaveBeenCalled(); // tab 1 was never asked to pause
    expect(b.pause).toHaveBeenCalledTimes(1);
  });

  it("lets the later start win when two tabs start one right after the other", () => {
    const bus = makeBus();
    const tab1 = createCoordinator({ channelFactory: bus.factory, tabId: "t1", now: () => 1000 });
    const tab2 = createCoordinator({ channelFactory: bus.factory, tabId: "t2", now: () => 1005 });
    const a = player(); const b = player();
    tab1.register("a", a); tab2.register("b", b);
    tab1.notifyPlaying("a");
    tab2.notifyPlaying("b"); // started later (1005 > 1000), so tab 1 pauses
    expect(a.pause).toHaveBeenCalledTimes(1);
    expect(tab2.getActiveId()).toBe("b");
  });

  it("keeps the local video when the other tab's message is older than this tab's start", () => {
    const bus = makeBus();
    const tab = createCoordinator({ channelFactory: bus.factory, tabId: "t1", now: () => 2000 });
    const a = player();
    tab.register("a", a);
    tab.notifyPlaying("a"); // stamped 2000
    bus.factory().postMessage({ v: 1, type: "playing", tabId: "t2", playerId: "b", at: 1000 }); // from another tab, older
    expect(a.pause).not.toHaveBeenCalled();
    expect(tab.getActiveId()).toBe("a");
  });

  it("breaks an exact tie with the tab id so exactly one tab keeps playing", () => {
    const bus = makeBus();
    const small = createCoordinator({ channelFactory: bus.factory, tabId: "a-tab", now: () => 500 });
    const large = createCoordinator({ channelFactory: bus.factory, tabId: "z-tab", now: () => 500 });
    const s = player(); const l = player();
    small.register("s", s); large.register("l", l);
    small.notifyPlaying("s"); // large had nothing active: pauses l
    large.notifyPlaying("l"); // same instant: z-tab wins, so small pauses s
    expect(s.pause).toHaveBeenCalledTimes(1);
    expect(large.getActiveId()).toBe("l");
  });

  it("ignores messages that are malformed, from itself, or of another version", () => {
    const bus = makeBus();
    const c = createCoordinator({ channelFactory: bus.factory, tabId: "me" });
    const a = player();
    c.register("a", a);
    const stranger = bus.factory();
    for (const data of [null, "x", {}, { v: 2, type: "playing", tabId: "t", at: 1 }, { v: 1, type: "other", tabId: "t", at: 1 },
      { v: 1, type: "playing", tabId: 5, at: 1 }, { v: 1, type: "playing", tabId: "t", at: "soon" }, { v: 1, type: "playing", tabId: "me", at: 1 }]) {
      stranger.postMessage(data);
    }
    expect(a.pause).not.toHaveBeenCalled();
  });

  it("opens the channel only while a player is registered", () => {
    const bus = makeBus();
    const c = createCoordinator({ channelFactory: bus.factory });
    expect(bus.open()).toBe(0);
    const stop1 = c.register("a", player());
    const stop2 = c.register("b", player());
    expect(bus.open()).toBe(1);
    stop1();
    expect(bus.open()).toBe(1);
    stop2();
    expect(bus.open()).toBe(0);
  });
});

describe("youtubeEmbedUrl with the player API switched on", () => {
  it("leaves the old addresses exactly as they were", () => {
    expect(youtubeEmbedUrl("dQw4w9WgXcQ")).toBe("https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ");
    expect(youtubeEmbedUrl("dQw4w9WgXcQ", { autoplay: true })).toBe("https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ?autoplay=1&mute=1&playsinline=1&rel=0");
  });

  it("adds enablejsapi and this site's origin when asked", () => {
    const plain = youtubeEmbedUrl("dQw4w9WgXcQ", { jsApi: true });
    expect(plain).toMatch(/^https:\/\/www\.youtube-nocookie\.com\/embed\/dQw4w9WgXcQ\?enablejsapi=1/);
    const auto = youtubeEmbedUrl("dQw4w9WgXcQ", { autoplay: true, jsApi: true });
    expect(auto).toMatch(/^https:\/\/www\.youtube-nocookie\.com\/embed\/dQw4w9WgXcQ\?autoplay=1&mute=1&playsinline=1&rel=0&enablejsapi=1/);
  });
});
