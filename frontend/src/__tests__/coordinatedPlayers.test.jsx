import { act, render } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// A fake YouTube player API. A player either ADOPTS an existing iframe (story embeds, marketplace previews) or builds its own
// (Academy lessons); either way the test drives its events by hand.
const created = [];
let loadResult;
class FakePlayer {
  constructor(target, opts) {
    this.target = target; this.opts = opts; this.state = -1; this.pauses = 0;
    created.push(this);
  }
  pauseVideo() { this.pauses += 1; }
  getPlayerState() { return this.state; }
  getCurrentTime() { return 0; }
  getDuration() { return 600; }
  destroy() {}
  emit(state) { this.state = state; this.opts.events.onStateChange({ data: state }); }
  ready() { this.opts.events.onReady({}); }
}
const fakeYT = { PlayerState: { ENDED: 0, PLAYING: 1, PAUSED: 2 }, Player: FakePlayer };
vi.mock("../player/youtubeApi", () => ({ loadYouTubeApi: () => loadResult() }));

import StoryRenderer from "../components/StoryRenderer";
import VideoPreview from "../components/marketplace/VideoPreview";
import { useLessonPlayer } from "../academy/player/useLessonPlayer";
import { coordinator } from "../player/VideoPlaybackCoordinator";

const story = (...ids) => ({ type: "doc", content: ids.map((videoId) => ({ type: "youtube", attrs: { videoId } })) });
function Lesson(props) {
  const { host } = useLessonPlayer({ onReport: () => {}, ...props });
  return <div ref={host} data-testid="lesson-host" />;
}
const flush = () => act(async () => { await Promise.resolve(); await Promise.resolve(); await Promise.resolve(); });
const byVideo = (id) => created.find((p) => p.opts.videoId === id);
const onIframe = (n) => created.filter((p) => p.target?.tagName === "IFRAME")[n];

beforeEach(() => {
  created.length = 0;
  loadResult = () => Promise.resolve(fakeYT);
  vi.stubGlobal("BroadcastChannel", undefined); // these tests are about players in ONE tab; tabs are covered in videoCoordinator.test.js
});
afterEach(() => vi.unstubAllGlobals());

describe("story embeds under the shared coordinator", () => {
  it("keeps the existing iframe and only adds what the player API needs", async () => {
    const { container } = render(<StoryRenderer content={story("dQw4w9WgXcQ")} />);
    const iframe = container.querySelector("iframe");
    expect(iframe.getAttribute("src")).toMatch(/^https:\/\/www\.youtube-nocookie\.com\/embed\/dQw4w9WgXcQ\?autoplay=1&mute=1&playsinline=1&rel=0&enablejsapi=1/);
    expect(iframe.getAttribute("title")).toBe("YouTube video");
    await flush();
    expect(created).toHaveLength(1);
    expect(created[0].target).toBe(iframe); // the player wraps the very iframe React rendered
  });

  it("pauses the first story video when a second one starts", async () => {
    render(<StoryRenderer content={story("aaaaaaaaaaa", "bbbbbbbbbbb")} />);
    await flush();
    const [first, second] = created;
    act(() => { first.ready(); second.ready(); });
    act(() => first.emit(1));
    expect(second.pauses).toBe(1); // the one that did not start is paused
    expect(first.pauses).toBe(0);
    act(() => second.emit(1));
    expect(first.pauses).toBe(1);
    expect(second.pauses).toBe(1); // unchanged: the one that just started is never paused
  });

  it("announces a video that was already autoplaying when the player API attached", async () => {
    render(<StoryRenderer content={story("aaaaaaaaaaa", "bbbbbbbbbbb")} />);
    await flush();
    const [first, second] = created;
    act(() => first.ready());
    second.state = 1; // autoplay had already started it
    act(() => second.ready());
    expect(first.pauses).toBe(1);
  });

  it("pauses a video that was told to pause before its player was ready, as soon as it is ready", async () => {
    render(<StoryRenderer content={story("aaaaaaaaaaa", "bbbbbbbbbbb")} />);
    await flush();
    const [first, second] = created;
    act(() => second.emit(1)); // second plays; first has not reported ready yet
    expect(first.pauses).toBe(0);
    act(() => first.ready());
    expect(first.pauses).toBe(1);
  });

  it("stops coordinating a video when its page goes away (route change)", async () => {
    const story1 = render(<StoryRenderer content={story("aaaaaaaaaaa")} />);
    await flush();
    const [gone] = created;
    expect(coordinator.playerCount()).toBe(1);
    story1.unmount();
    expect(coordinator.playerCount()).toBe(0);
    const story2 = render(<StoryRenderer content={story("bbbbbbbbbbb")} />);
    await flush();
    act(() => created[1].emit(1));
    expect(gone.pauses).toBe(0);
    story2.unmount();
    expect(coordinator.playerCount()).toBe(0);
  });

  it("ignores events that arrive after unmount, and a player that never loads leaves the embed working", async () => {
    const { unmount, container } = render(<StoryRenderer content={story("aaaaaaaaaaa")} />);
    await flush();
    const [p] = created;
    unmount();
    expect(() => act(() => p.emit(1))).not.toThrow();
    created.length = 0;
    loadResult = () => Promise.reject(new Error("blocked"));
    const failed = render(<StoryRenderer content={story("ccccccccccc")} />);
    await flush();
    expect(failed.container.querySelector("iframe")).toBeTruthy();
    expect(created).toHaveLength(0);
    expect(container).toBeTruthy();
  });

  it("does not attach a player for a bad id (nothing is rendered)", async () => {
    render(<StoryRenderer content={story('x" onload="y')} />);
    await flush();
    expect(created).toHaveLength(0);
  });
});

describe("one video at a time across stories, marketplace previews and Academy lessons", () => {
  it("a lesson starting pauses the story video, and the story starting pauses the lesson", async () => {
    render(<StoryRenderer content={story("aaaaaaaaaaa")} />);
    render(<Lesson videoId="lllllllllll" />);
    await flush();
    const storyPlayer = onIframe(0);
    const lessonPlayer = byVideo("lllllllllll");
    act(() => { storyPlayer.ready(); lessonPlayer.opts.events.onReady(); });
    act(() => lessonPlayer.emit(1));
    expect(storyPlayer.pauses).toBe(1);
    expect(lessonPlayer.pauses).toBe(0);
    act(() => storyPlayer.emit(1));
    expect(lessonPlayer.pauses).toBe(1);
  });

  it("covers the marketplace demo video too", async () => {
    const { container } = render(<VideoPreview id="dQw4w9WgXcQ" title="Shop" />);
    expect(container.querySelector("iframe").getAttribute("src")).toMatch(/enablejsapi=1/);
    render(<Lesson videoId="lllllllllll" />);
    await flush();
    const preview = onIframe(0);
    act(() => preview.ready());
    act(() => byVideo("lllllllllll").emit(1));
    expect(preview.pauses).toBe(1);
  });

  it("renders nothing and attaches nothing for an invalid marketplace id", async () => {
    const { container } = render(<VideoPreview id="nope" title="Shop" />);
    await flush();
    expect(container.querySelector("iframe")).toBeNull();
    expect(created).toHaveLength(0);
  });

  it("a lesson that is torn down stops being coordinated", async () => {
    const lesson = render(<Lesson videoId="lllllllllll" />);
    render(<StoryRenderer content={story("aaaaaaaaaaa")} />);
    await flush();
    const lessonPlayer = byVideo("lllllllllll");
    lesson.unmount();
    act(() => onIframe(0).emit(1));
    expect(lessonPlayer.pauses).toBe(0);
  });

  it("registers each player once, even when the page re-renders", async () => {
    const { rerender } = render(<StoryRenderer content={story("aaaaaaaaaaa")} />);
    await flush();
    rerender(<StoryRenderer content={story("aaaaaaaaaaa")} />);
    await flush();
    expect(created).toHaveLength(1);
    expect(coordinator.playerCount()).toBe(1);
  });

  it("attaches a fresh player when the story's video changes", async () => {
    const { rerender, container } = render(<StoryRenderer content={story("aaaaaaaaaaa")} />);
    await flush();
    rerender(<StoryRenderer content={story("bbbbbbbbbbb")} />);
    await flush();
    expect(created).toHaveLength(2);
    expect(created[1].target).toBe(container.querySelector("iframe"));
    expect(coordinator.playerCount()).toBe(1);
  });
});
