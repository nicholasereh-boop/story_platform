import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor } from "@testing-library/react";
import { member, renderAt, resetBrowser } from "./extensionHarness";

let currentUser = null;
vi.mock("../api/client", async (importOriginal) => ({ ...(await importOriginal()), ensureCsrf: vi.fn().mockResolvedValue({}) }));
vi.mock("../api", () => ({
  me: vi.fn(() => (currentUser ? Promise.resolve(currentUser) : Promise.reject(new Error("no session")))),
  login: vi.fn(), logout: vi.fn(), providers: vi.fn().mockResolvedValue({ google: false }),
}));
vi.mock("../api/engagement", () => ({ getLikes: vi.fn(), likeStory: vi.fn(), unlikeStory: vi.fn(), listComments: vi.fn(), createComment: vi.fn(), editComment: vi.fn(), deleteComment: vi.fn(), reportComment: vi.fn() }));
vi.mock("../analytics/tracker", async (importOriginal) => ({ ...(await importOriginal()), sendPageView: vi.fn() }));
vi.mock("../api/public", () => ({ getStories: vi.fn(), getStory: vi.fn(), getRelatedStories: vi.fn(), getCategories: vi.fn(), getCategoryStories: vi.fn(), getTags: vi.fn(), searchStories: vi.fn() }));
vi.mock("../api/security", () => ({ getPublicConfig: vi.fn().mockResolvedValue({ site_name: "StoryBoard", consent_mode: "notice", analytics_enabled: false, contact_email: "" }), getPrivacyPolicy: vi.fn() }));
vi.mock("../api/videoTools", async (importOriginal) => ({
  ...(await importOriginal()),
  inspectLink: vi.fn(), requestDownload: vi.fn(), getJob: vi.fn(), removeJob: vi.fn(), fetchJobFile: vi.fn(),
}));
vi.mock("../utils/saveBlob", async (importOriginal) => ({ ...(await importOriginal()), saveBlob: vi.fn() }));

import * as vt from "../api/videoTools";
import { saveBlob } from "../utils/saveBlob";

const YT = "https://www.youtube.com/watch?v=dQw4w9WgXcQ";
const err = (message, fieldErrors = {}, status = 400) => Object.assign(new Error(message), { friendly: message, fieldErrors, status });
const closed = {
  provider: "youtube", provider_label: "YouTube", content_kind: "video", content_id: "dQw4w9WgXcQ", canonical_url: YT, needs_resolution: false,
  download: { available: false, reason: "No permitted download method is set up for YouTube on this site.", method: "", formats: [] },
  guidance: "YouTube's terms generally only allow downloading through features YouTube itself provides.",
  notice: "Platforms may add a watermark. This tool never removes watermarks, never bypasses access restrictions or DRM.",
};
const open = { ...closed, download: { available: true, reason: "", method: "Official export of your own video.", formats: [{ key: "mp4", label: "MP4 video" }, { key: "mp3", label: "Audio only" }] } };
const job = (over = {}) => ({ id: "5b0f6a10-0000-4000-8000-000000000001", provider: "youtube", provider_label: "YouTube", source_url: YT, format_key: "mp4", status: "queued", error_code: "", error_message: "", created_at: "2026-10-18T10:00:00Z", artifact: null, ...over });
const done = job({ status: "done", artifact: { filename: "My Video.mp4", size_bytes: 900, content_type: "video/mp4", expires_at: "2026-10-19T10:00:00Z" } });

async function check(url = YT) {
  fireEvent.change(await screen.findByLabelText("Video link"), { target: { value: url } });
  fireEvent.click(screen.getByRole("button", { name: "Check link" }));
}

beforeEach(() => {
  resetBrowser();
  currentUser = null;
});

describe("video tools: checking a link", () => {
  it("is reachable without logging in, and says nothing can be downloaded when no permitted method exists", async () => {
    vt.inspectLink.mockResolvedValue(closed);
    renderAt("/video-tools");
    await check();
    expect(await screen.findByText("Downloading is not available for this link")).toBeInTheDocument();
    expect(screen.getByText(/No permitted download method is set up for YouTube/)).toBeInTheDocument();
    expect(screen.getByText(/generally only allow downloading through features YouTube itself provides/)).toBeInTheDocument();
    expect(screen.getByText(/never removes watermarks/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Start download" })).toBeNull(); // no button that cannot work
    expect(vt.inspectLink).toHaveBeenCalledWith(YT);
    expect(vt.requestDownload).not.toHaveBeenCalled();
  });

  it("shows the server's message for a bad link and keeps the person's text", async () => {
    vt.inspectLink.mockRejectedValue(err("x", { url: ["We only work with links from YouTube, Facebook, Instagram, TikTok and X."] }));
    renderAt("/video-tools");
    await check("https://evil.example/x");
    expect(await screen.findByRole("alert")).toHaveTextContent("We only work with links from YouTube");
    expect(screen.getByLabelText("Video link")).toHaveValue("https://evil.example/x");
  });

  it("disables the button for an empty box", async () => {
    renderAt("/video-tools");
    const button = await screen.findByRole("button", { name: "Check link" });
    expect(button.disabled).toBe(true);
  });

  it("explains short links instead of offering to download them", async () => {
    currentUser = member;
    vt.inspectLink.mockResolvedValue({ ...open, provider: "tiktok", provider_label: "TikTok", needs_resolution: true });
    renderAt("/video-tools");
    await check("https://vm.tiktok.com/ZMabc123/");
    expect(await screen.findByText("This is a shortened link")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Start download" })).toBeNull();
  });
});

describe("video tools: downloading where a permitted method exists", () => {
  it("asks anonymous visitors to log in first", async () => {
    vt.inspectLink.mockResolvedValue(open);
    renderAt("/video-tools");
    await check();
    expect(await screen.findByRole("link", { name: "Log in" })).toHaveAttribute("href", "/login");
    expect(screen.queryByRole("button", { name: "Start download" })).toBeNull();
  });

  it("will not start until the person confirms they have permission", async () => {
    currentUser = member;
    vt.inspectLink.mockResolvedValue(open);
    renderAt("/video-tools");
    await check();
    const start = await screen.findByRole("button", { name: "Start download" });
    expect(start.disabled).toBe(true);
    expect(screen.getByText(/Method: Official export of your own video\./)).toBeInTheDocument();
    fireEvent.click(screen.getByLabelText(/I own this video or have permission/));
    expect(start.disabled).toBe(false);
  });

  it("sends the canonical link, the chosen format and the confirmation, then follows the job to a saved file", async () => {
    currentUser = member;
    vt.inspectLink.mockResolvedValue(open);
    vt.requestDownload.mockResolvedValue(job());
    vt.getJob.mockResolvedValueOnce(job({ status: "processing" })).mockResolvedValue(done);
    vt.fetchJobFile.mockResolvedValue({ blob: new Blob(["v"]), filename: "My Video.mp4" });
    renderAt("/video-tools");
    await check(YT + "&utm_source=x");
    fireEvent.change(await screen.findByLabelText("Format"), { target: { value: "mp3" } });
    fireEvent.click(screen.getByLabelText(/I own this video or have permission/));
    fireEvent.click(screen.getByRole("button", { name: "Start download" }));
    await waitFor(() => expect(vt.requestDownload).toHaveBeenCalledWith({ url: YT, format: "mp3", authorizationConfirmed: true }));
    expect(await screen.findByText(/Your file is ready/, {}, { timeout: 4000 })).toBeInTheDocument();
    expect(screen.getByText(/deleted automatically/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Save file" }));
    await waitFor(() => expect(saveBlob).toHaveBeenCalledWith(expect.any(Blob), "My Video.mp4"));
    expect(vt.fetchJobFile).toHaveBeenCalledWith(done.id, "My Video.mp4");
  }, 10000);

  it("shows why a job failed, in the server's words, and offers a fresh start", async () => {
    currentUser = member;
    vt.inspectLink.mockResolvedValue(open);
    vt.requestDownload.mockResolvedValue(job({ status: "failed", error_message: "The uploader has not allowed downloads." }));
    vt.getJob.mockResolvedValue(job({ status: "failed", error_message: "The uploader has not allowed downloads." }));
    renderAt("/video-tools");
    await check();
    fireEvent.click(await screen.findByLabelText(/I own this video or have permission/));
    fireEvent.click(screen.getByRole("button", { name: "Start download" }));
    expect(await screen.findByText("The uploader has not allowed downloads.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Check another link" }));
    expect(screen.getByLabelText("Video link")).toHaveValue("");
  });

  it("shows a refusal (limits, provider switched off) without creating a job", async () => {
    currentUser = member;
    vt.inspectLink.mockResolvedValue(open);
    vt.requestDownload.mockRejectedValue(err("You already have downloads in progress. Wait for them to finish.", { code: "too_many_active", detail: "You already have downloads in progress. Wait for them to finish." }, 429));
    renderAt("/video-tools");
    await check();
    fireEvent.click(await screen.findByLabelText(/I own this video or have permission/));
    fireEvent.click(screen.getByRole("button", { name: "Start download" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("You already have downloads in progress");
    expect(vt.getJob).not.toHaveBeenCalled();
  });

  it("lets the person cancel a running job and delete a finished file", async () => {
    currentUser = member;
    vt.inspectLink.mockResolvedValue(open);
    vt.requestDownload.mockResolvedValue(job());
    vt.getJob.mockResolvedValue(job({ status: "processing" }));
    vt.removeJob.mockResolvedValue({});
    renderAt("/video-tools");
    await check();
    fireEvent.click(await screen.findByLabelText(/I own this video or have permission/));
    fireEvent.click(screen.getByRole("button", { name: "Start download" }));
    fireEvent.click(await screen.findByRole("button", { name: "Cancel" }));
    await waitFor(() => expect(vt.removeJob).toHaveBeenCalledWith(job().id));
  });
});
