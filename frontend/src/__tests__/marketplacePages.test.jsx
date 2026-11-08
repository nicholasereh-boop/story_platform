import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { card, detail, member, offer, page, renderAt, resetBrowser, staff } from "./extensionHarness";

let currentUser = null;
vi.mock("../api/client", async (importOriginal) => ({ ...(await importOriginal()), ensureCsrf: vi.fn().mockResolvedValue({}) }));
vi.mock("../api", () => ({
  me: vi.fn(() => (currentUser ? Promise.resolve(currentUser) : Promise.reject(new Error("no session")))),
  login: vi.fn(), logout: vi.fn(), providers: vi.fn().mockResolvedValue({ google: false }),
}));
vi.mock("../api/engagement", () => ({ getLikes: vi.fn(), likeStory: vi.fn(), unlikeStory: vi.fn(), listComments: vi.fn(), createComment: vi.fn(), editComment: vi.fn(), deleteComment: vi.fn(), reportComment: vi.fn() }));
vi.mock("../analytics/tracker", async (importOriginal) => ({ ...(await importOriginal()), sendPageView: vi.fn() }));
vi.mock("../api/public", () => ({ getStories: vi.fn(), getStory: vi.fn(), getRelatedStories: vi.fn(), getCategories: vi.fn(), getCategoryStories: vi.fn(), getTags: vi.fn(), searchStories: vi.fn() }));
vi.mock("../api/security", () => ({
  getPublicConfig: vi.fn().mockResolvedValue({ site_name: "StoryBoard", consent_mode: "notice", analytics_enabled: false, contact_email: "" }),
  getPrivacyPolicy: vi.fn(),
}));
vi.mock("../api/marketplace", () => ({
  listProjects: vi.fn(), listTechnologies: vi.fn(), getProject: vi.fn(), createProject: vi.fn(), updateProject: vi.fn(), deleteProject: vi.fn(),
  myProjects: vi.fn(), myProject: vi.fn(), submitProject: vi.fn(), unpublishProject: vi.fn(), archiveProject: vi.fn(),
  uploadScreenshots: vi.fn(), deleteScreenshot: vi.fn(), uploadPackage: vi.fn(), importFromGitHub: vi.fn(), removePackage: vi.fn(),
  getMarketplaceConfig: vi.fn(), startCheckout: vi.fn(), verifyPayment: vi.fn(), myPurchases: vi.fn(), downloadPackage: vi.fn(), adminProjects: vi.fn(), moderateProject: vi.fn(),
}));
vi.mock("../utils/saveBlob", async (importOriginal) => ({ ...(await importOriginal()), saveBlob: vi.fn() }));

import * as mp from "../api/marketplace";
import { saveBlob } from "../utils/saveBlob";

const err = (message, fieldErrors = {}, status = 400) => Object.assign(new Error(message), { friendly: message, fieldErrors, status });

beforeEach(() => {
  resetBrowser();
  currentUser = null;
  mp.listTechnologies.mockResolvedValue([{ name: "React", slug: "react" }]);
  mp.getMarketplaceConfig.mockResolvedValue({ currency: "USD", backend_requires_payment: true, max_price: 10000, payments_enabled: true });
  mp.listProjects.mockResolvedValue(page([card()]));
});

describe("marketplace listing", () => {
  it("lists published projects with their prices and links to them", async () => {
    mp.listProjects.mockResolvedValue(page([card(), card({ id: 6, slug: "api-kit", title: "API Kit", offers: [offer({ kind: "backend", price: "5000.00", is_free: false })] })]));
    renderAt("/marketplace");
    expect(await screen.findByRole("heading", { name: "Shop Template" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Shop Template/ })).toHaveAttribute("href", "/marketplace/projects/shop-template");
    expect(screen.getByText(/Frontend · Free/)).toBeInTheDocument();
    expect(screen.getByText(/Backend · \$5,000\.00/)).toBeInTheDocument();
    expect(document.title).toMatch(/Source code marketplace/);
  });

  it("sends the filters to the server and shows an empty state", async () => {
    renderAt("/marketplace");
    await screen.findByText("Shop Template");
    mp.listProjects.mockResolvedValue(page([]));
    fireEvent.change(screen.getByLabelText("Search"), { target: { value: "blog" } });
    fireEvent.click(screen.getByLabelText("Free only"));
    await waitFor(() => expect(mp.listProjects).toHaveBeenLastCalledWith({ q: "blog", tech: undefined, free: 1, page: 1 }));
    expect(await screen.findByText(/No projects match/)).toBeInTheDocument();
  });

  it("never turns a hostile image address into an <img>", async () => {
    mp.listProjects.mockResolvedValue(page([card({ cover: { url: "javascript:alert(1)", alt_text: "x" } })]));
    const { container } = renderAt("/marketplace");
    await screen.findByText("Shop Template");
    expect(container.querySelector("img")).toBeNull();
  });
});

describe("project page", () => {
  it("shows text as text, never as HTML", async () => {
    mp.getProject.mockResolvedValue(detail({ description: "Hello <img src=x onerror=alert(1)> <script>alert(2)</script>", notes: "<b>bold?</b>" }));
    const { container } = renderAt("/marketplace/projects/shop-template");
    expect(await screen.findByText(/Hello <img src=x onerror=alert\(1\)>/)).toBeInTheDocument();
    expect(container.querySelector("script")).toBeNull();
    expect(container.querySelector("img[onerror]")).toBeNull();
    expect(screen.getByText("<b>bold?</b>")).toBeInTheDocument();
  });

  it("embeds only a valid 11-character YouTube id, via the no-cookie player", async () => {
    mp.getProject.mockResolvedValue(detail({ youtube_id: "dQw4w9WgXcQ" }));
    const { container, unmount } = renderAt("/marketplace/projects/shop-template");
    await screen.findByText("Full description of the shop.");
    expect(container.querySelector("iframe").getAttribute("src")).toMatch(/^https:\/\/www\.youtube-nocookie\.com\/embed\/dQw4w9WgXcQ(\?enablejsapi=1.*)?$/); // jsApi lets the shared video coordinator watch it
    unmount();
    mp.getProject.mockResolvedValue(detail({ youtube_id: '"><script>' }));
    const second = renderAt("/marketplace/projects/shop-template");
    await screen.findByText("Full description of the shop.");
    expect(second.container.querySelector("iframe")).toBeNull();
  });

  it("is a clean 404 for an unknown project and is not indexed unless published", async () => {
    mp.getProject.mockRejectedValue(err("Not found.", {}, 404));
    renderAt("/marketplace/projects/nope");
    expect(await screen.findByText("That project could not be found")).toBeInTheDocument();
  });

  it("noindexes a draft that its owner is previewing", async () => {
    currentUser = member;
    mp.getProject.mockResolvedValue(detail({ status: "draft", viewer: { is_owner: true, packages: { frontend: { can_download: true, basis: "owner", purchased: false } } } }));
    renderAt("/marketplace/projects/shop-template");
    expect(await screen.findByText(/This is your project/)).toBeInTheDocument();
    expect(document.head.querySelector('meta[name="robots"]')).toHaveAttribute("content", "noindex");
  });
});

describe("getting a package", () => {
  it("asks anonymous visitors to log in (free and paid)", async () => {
    mp.getProject.mockResolvedValue(detail({ offers: [offer(), offer({ package_id: 12, kind: "backend", price: "5000.00", is_free: false })], viewer: { is_owner: false, packages: { frontend: { can_download: false }, backend: { can_download: false } } } }));
    renderAt("/marketplace/projects/shop-template");
    expect(await screen.findByRole("link", { name: "Log in to download" })).toHaveAttribute("href", "/login");
    expect(screen.getByRole("link", { name: "Log in to download backend · $5,000.00" })).toBeInTheDocument();
    expect(mp.startCheckout).not.toHaveBeenCalled();
  });

  it("downloads a package the reader may have, through the authorised endpoint", async () => {
    currentUser = member;
    mp.getProject.mockResolvedValue(detail());
    mp.downloadPackage.mockResolvedValue({ blob: new Blob(["zip"]), filename: "shop-template-frontend-v1.2.0.zip" });
    renderAt("/marketplace/projects/shop-template");
    fireEvent.click(await screen.findByRole("button", { name: /Download frontend package/ }));
    await waitFor(() => expect(saveBlob).toHaveBeenCalledWith(expect.any(Blob), "shop-template-frontend-v1.2.0.zip"));
    expect(mp.downloadPackage).toHaveBeenCalledWith(11, "shop-template-frontend.zip");
  });

  it("shows the server's reason when a download is refused", async () => {
    currentUser = member;
    mp.getProject.mockResolvedValue(detail());
    mp.downloadPackage.mockRejectedValue(err("Buy this package to download it.", {}, 403));
    renderAt("/marketplace/projects/shop-template");
    fireEvent.click(await screen.findByRole("button", { name: /Download frontend package/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Buy this package to download it.");
    expect(saveBlob).not.toHaveBeenCalled();
  });

  const paid = () => detail({ offers: [offer({ package_id: 12, kind: "backend", price: "5000.50", is_free: false })], viewer: { is_owner: false, packages: { backend: { can_download: false, purchased: false } } } });

  it("starts a payment on the server and only follows an https Paystack address", async () => {
    currentUser = member;
    mp.getProject.mockResolvedValue(paid());
    mp.startCheckout.mockResolvedValue({ reference: "rb_1", authorization_url: "https://checkout.paystack.com/abc", amount: "5000.50", currency: "USD" });
    const assign = vi.fn();
    vi.stubGlobal("location", { ...window.location, assign });
    renderAt("/marketplace/projects/shop-template");
    fireEvent.click(await screen.findByRole("button", { name: "Download backend package · $5,000.50" }));
    await waitFor(() => expect(assign).toHaveBeenCalledWith("https://checkout.paystack.com/abc"));
    expect(mp.startCheckout).toHaveBeenCalledWith(5, "backend"); // only the project and package kind: the PRICE is never sent
    vi.unstubAllGlobals();
  });

  it.each(["javascript:alert(1)", "http://checkout.example/x", "//evil.example/x", ""])("refuses to navigate to %j", async (url) => {
    currentUser = member;
    mp.getProject.mockResolvedValue(paid());
    mp.startCheckout.mockResolvedValue({ authorization_url: url });
    const assign = vi.fn();
    vi.stubGlobal("location", { ...window.location, assign });
    renderAt("/marketplace/projects/shop-template");
    fireEvent.click(await screen.findByRole("button", { name: /Download backend package/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/could not start the payment/i);
    expect(assign).not.toHaveBeenCalled();
    vi.unstubAllGlobals();
  });

  it("tells a paying reader, before they click, that Paystack comes first and what it costs in dollars", async () => {
    currentUser = member;
    mp.getProject.mockResolvedValue(paid());
    renderAt("/marketplace/projects/shop-template");
    await screen.findByRole("button", { name: "Download backend package · $5,000.50" });
    expect(screen.getByRole("note")).toHaveTextContent("You will pay $5,000.50 securely with Paystack first, then the download unlocks.");
    expect(mp.downloadPackage).not.toHaveBeenCalled(); // clicking leads to payment, never straight to a file
  });

  it("a paid package that the reader already bought is a plain download, with no payment note", async () => {
    currentUser = member;
    mp.getProject.mockResolvedValue({ ...paid(), viewer: { is_owner: false, packages: { backend: { can_download: true, basis: "purchase", purchased: true } } } });
    renderAt("/marketplace/projects/shop-template");
    await screen.findByRole("button", { name: "Download backend package" });
    expect(screen.queryByRole("note")).toBeNull();
    expect(mp.startCheckout).not.toHaveBeenCalled();
  });

  it("a free package never mentions payment", async () => {
    currentUser = member;
    mp.getProject.mockResolvedValue(detail({ viewer: { is_owner: false, packages: { frontend: { can_download: true, basis: "free", purchased: false } } } }));
    renderAt("/marketplace/projects/shop-template");
    await screen.findByRole("button", { name: /Download frontend package/ });
    expect(screen.queryByText(/Paystack/)).toBeNull();
  });

  it("reports a payment problem from the server", async () => {
    currentUser = member;
    mp.getProject.mockResolvedValue(paid());
    mp.startCheckout.mockRejectedValue(err("Payments are not available right now.", {}, 503));
    renderAt("/marketplace/projects/shop-template");
    fireEvent.click(await screen.findByRole("button", { name: /Download backend package/ }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Payments are not available right now.");
  });
});

describe("purchases and payment return", () => {
  const purchase = (over = {}) => ({ id: 1, reference: "rb_1", status: "success", amount: "5000.50", currency: "NGN", project: { id: 5, slug: "shop-template", title: "Shop Template" }, kind: "backend", package_id: 12, version: "1.2.0", can_download: true, ...over });

  it("requires a login", async () => {
    const { router } = renderAt("/marketplace/purchases");
    await waitFor(() => expect(router.state.location.pathname).toBe("/login"));
  });

  it("confirms the payment with the SERVER and keeps the message after the address is cleaned", async () => {
    currentUser = member;
    mp.myPurchases.mockResolvedValue(page([purchase()]));
    mp.verifyPayment.mockResolvedValue(purchase());
    const { router } = renderAt("/marketplace/purchases?reference=rb_1");
    expect(await screen.findByText(/Payment confirmed/)).toBeInTheDocument();
    expect(mp.verifyPayment).toHaveBeenCalledTimes(1);
    expect(mp.verifyPayment).toHaveBeenCalledWith("rb_1");
    await waitFor(() => expect(router.state.location.search).toBe(""));
    expect(screen.getByText(/Payment confirmed/)).toBeInTheDocument(); // still there
    expect(await screen.findByRole("button", { name: "Download" })).toBeInTheDocument();
  });

  it("does not claim success when the payment failed or is pending", async () => {
    currentUser = member;
    mp.myPurchases.mockResolvedValue(page([purchase({ status: "failed", can_download: false })]));
    mp.verifyPayment.mockResolvedValue(purchase({ status: "failed", can_download: false }));
    renderAt("/marketplace/purchases?reference=rb_1");
    expect(await screen.findByText(/did not go through/)).toBeInTheDocument();
    expect(screen.queryByText(/Payment confirmed/)).toBeNull();
    expect(screen.queryByRole("button", { name: "Download" })).toBeNull();
  });

  it("lets the buyer try again when Paystack could not be reached", async () => {
    currentUser = member;
    mp.myPurchases.mockResolvedValue(page([]));
    mp.verifyPayment.mockRejectedValueOnce(err("The payment provider could not be reached.", {}, 502)).mockResolvedValueOnce(purchase());
    renderAt("/marketplace/purchases?reference=rb_1");
    fireEvent.click(await screen.findByRole("button", { name: "Check again" }));
    expect(await screen.findByText(/Payment confirmed/)).toBeInTheDocument();
  });
});

describe("selling", () => {
  it("requires a login to sell", async () => {
    const { router } = renderAt("/marketplace/publish");
    await waitFor(() => expect(router.state.location.pathname).toBe("/login"));
  });

  it("creates a draft and moves on to the editor", async () => {
    currentUser = member;
    mp.createProject.mockResolvedValue({ id: 9, title: "My Kit" });
    mp.myProject.mockResolvedValue({ ...detail({ id: 9, title: "My Kit", status: "draft" }), packages: [], frontend_price: "0.00", backend_price: "0.00", rights_confirmed_at: null, review_note: "" });
    const { router } = renderAt("/marketplace/publish");
    fireEvent.change(await screen.findByLabelText("Title"), { target: { value: "My Kit" } });
    fireEvent.change(screen.getByLabelText(/Technologies/), { target: { value: "React, Django ,," } });
    fireEvent.change(screen.getByLabelText("Frontend price in USD (0 = free)"), { target: { value: "2500" } });
    fireEvent.click(screen.getByLabelText(/I own this code/));
    fireEvent.click(screen.getByRole("button", { name: "Create draft" }));
    await waitFor(() => expect(mp.createProject).toHaveBeenCalled());
    expect(mp.createProject.mock.calls[0][0]).toMatchObject({ title: "My Kit", technologies: ["React", "Django"], frontend_price: "2500", backend_price: "0", rights_confirmed: true });
    await waitFor(() => expect(router.state.location.pathname).toBe("/marketplace/projects/9/edit"));
  });

  it("prices are labelled in dollars, and the seller is told backend code is always paid", async () => {
    currentUser = member;
    renderAt("/marketplace/publish");
    expect(await screen.findByLabelText("Frontend price in USD (0 = free)")).toBeInTheDocument();
    expect(screen.getByLabelText("Backend price in USD")).toBeInTheDocument();
    expect(screen.getByText(/Backend source code is always paid: buyers pay with Paystack before they can download it/)).toBeInTheDocument();
  });

  it("an older project keeps the currency it was priced in (never silently re-labelled as dollars)", async () => {
    currentUser = member;
    mp.myProject.mockResolvedValue({ ...detail({ id: 9, status: "draft", currency: "NGN" }), packages: [], frontend_price: "0.00", backend_price: "5000.00", rights_confirmed_at: null, review_note: "" });
    renderAt("/marketplace/projects/9/edit");
    expect(await screen.findByLabelText("Backend price in NGN")).toBeInTheDocument();
  });

  it("shows the server's reason when a backend package has no price", async () => {
    currentUser = member;
    mp.myProject.mockResolvedValue({ ...detail({ id: 9, status: "draft" }), packages: [{ ...offer({ kind: "backend" }), scan_report: {}, source_ref: "", sha256: "a" }], frontend_price: "0.00", backend_price: "0.00", rights_confirmed_at: "2026-10-01T00:00:00Z", review_note: "" });
    mp.submitProject.mockRejectedValue(err("x", { backend_price: ["Backend source code is sold, not given away. Set a price above 0 (USD)."] }));
    renderAt("/marketplace/projects/9/edit");
    fireEvent.click(await screen.findByRole("button", { name: "Submit for publishing" }));
    expect(await screen.findByText(/Set a price above 0 \(USD\)/)).toBeInTheDocument();
  });

  it("shows the server's field errors under the right fields", async () => {
    currentUser = member;
    mp.createProject.mockRejectedValue(err("Please correct the highlighted fields.", { title: ["Remove the markup."], backend_price: ["The highest price allowed is 10,000 USD."] }));
    renderAt("/marketplace/publish");
    fireEvent.change(await screen.findByLabelText("Title"), { target: { value: "x" } });
    fireEvent.click(screen.getByRole("button", { name: "Create draft" }));
    expect(await screen.findByText("Remove the markup.")).toBeInTheDocument();
    expect(screen.getByText(/highest price allowed/)).toBeInTheDocument();
  });

  const editable = (over = {}) => ({
    ...detail({ id: 9, status: "draft", ...over }), packages: [{ ...offer(), scan_report: { excluded_count: 3, excluded: [{ path: ".env", reason: "environment file (may hold secrets)" }], symlinks_removed: 0, root_folder_removed: "shop-main" }, source_ref: "", sha256: "a" }],
    frontend_price: "0.00", backend_price: "0.00", rights_confirmed_at: "2026-10-01T00:00:00Z", review_note: "",
  });

  it("explains what the upload check removed and uploads a ZIP", async () => {
    currentUser = member;
    mp.myProject.mockResolvedValue(editable());
    mp.uploadPackage.mockResolvedValue(editable());
    renderAt("/marketplace/projects/9/edit");
    expect(await screen.findByText(/3 files left out/)).toBeInTheDocument();
    expect(screen.getByText(/shop-main/)).toBeInTheDocument();
    const section = screen.getByRole("heading", { name: "Backend package" }).closest("section");
    const file = new File(["zip"], "backend.zip", { type: "application/zip" });
    fireEvent.change(within(section).getByLabelText("Upload a ZIP"), { target: { files: [file] } });
    fireEvent.click(within(section).getByRole("button", { name: "Upload ZIP" }));
    await waitFor(() => expect(mp.uploadPackage).toHaveBeenCalled());
    expect(mp.uploadPackage.mock.calls[0][1]).toMatchObject({ kind: "backend", file });
  });

  it("shows the upload check's message when an archive is rejected", async () => {
    currentUser = member;
    mp.myProject.mockResolvedValue(editable());
    mp.uploadPackage.mockRejectedValue(err("x", { file: ["Possible secrets were found in: config.py (looks like an AWS access key)."] }));
    renderAt("/marketplace/projects/9/edit");
    const section = (await screen.findByRole("heading", { name: "Backend package" })).closest("section");
    fireEvent.change(within(section).getByLabelText("Upload a ZIP"), { target: { files: [new File(["x"], "b.zip")] } });
    fireEvent.click(within(section).getByRole("button", { name: "Upload ZIP" }));
    expect(await within(section).findByRole("alert")).toHaveTextContent("Possible secrets were found in: config.py");
  });

  it("clears the GitHub token from the page as soon as it was used, success or not", async () => {
    currentUser = member;
    mp.myProject.mockResolvedValue(editable());
    mp.importFromGitHub.mockRejectedValue(err("x", { repository: ["Repository or branch not found."] }));
    renderAt("/marketplace/projects/9/edit");
    const section = (await screen.findByRole("heading", { name: "Backend package" })).closest("section");
    fireEvent.click(within(section).getByText("Import from GitHub instead"));
    fireEvent.change(within(section).getByLabelText("Repository"), { target: { value: "acme/shop" } });
    const token = within(section).getByLabelText(/Access token/);
    expect(token).toHaveAttribute("type", "password");
    fireEvent.change(token, { target: { value: "github_pat_ABCDEF123456" } });
    fireEvent.click(within(section).getByRole("button", { name: "Import from GitHub" }));
    expect(await within(section).findByText("Repository or branch not found.")).toBeInTheDocument();
    expect(mp.importFromGitHub.mock.calls[0][1]).toMatchObject({ kind: "backend", repository: "acme/shop", token: "github_pat_ABCDEF123456" });
    expect(token).toHaveValue("");
    expect(JSON.stringify({ ...localStorage })).not.toMatch(/github_pat/);
  });

  it("lists the server's reasons when submitting is not yet possible, and tells the seller about review", async () => {
    currentUser = member;
    mp.myProject.mockResolvedValue(editable());
    mp.submitProject.mockRejectedValueOnce(err("x", { rights_confirmed: ["Confirm that you own this code or are allowed to distribute it."] }));
    renderAt("/marketplace/projects/9/edit");
    fireEvent.click(await screen.findByRole("button", { name: "Submit for publishing" }));
    expect(await screen.findByText(/Confirm that you own this code/)).toBeInTheDocument();
    mp.submitProject.mockResolvedValueOnce(editable({ status: "pending" }));
    fireEvent.click(screen.getByRole("button", { name: "Submit for publishing" }));
    expect(await screen.findByText(/A reviewer will check this project/)).toBeInTheDocument();
  });

  it("shows a rejection note to the seller", async () => {
    currentUser = member;
    mp.myProject.mockResolvedValue({ ...editable({ status: "rejected" }), review_note: "Please remove the licence conflict." });
    renderAt("/marketplace/projects/9/edit");
    expect(await screen.findByText(/Please remove the licence conflict\./)).toBeInTheDocument();
  });
});

describe("staff review", () => {
  const queued = { ...card({ id: 8, title: "Queued Kit" }), status: "pending", owner_email: "seller@example.com", rights_confirmed_at: "2026-10-01T00:00:00Z", review_note: "", description: "d".repeat(500), packages: [{ ...offer(), scan_report: { excluded_count: 2 }, source_ref: "" }] };

  it("is for staff only", async () => {
    currentUser = member;
    const { router } = renderAt("/admin/marketplace");
    await waitFor(() => expect(router.state.location.pathname).toBe("/"));
    expect(mp.adminProjects).not.toHaveBeenCalled();
  });

  it("has an Add source code button that opens the new-project form", async () => {
    currentUser = staff;
    mp.adminProjects.mockResolvedValue(page([]));
    mp.createProject.mockResolvedValue({ id: 9 });
    const { router } = renderAt("/admin/marketplace");
    const add = await screen.findByRole("link", { name: "Add source code" });
    expect(add).toHaveAttribute("href", "/marketplace/publish");
    fireEvent.click(add);
    await waitFor(() => expect(router.state.location.pathname).toBe("/marketplace/publish"));
    expect(await screen.findByRole("heading", { name: "Sell your source code" })).toBeInTheDocument();
  });

  it("approves, and requires a note to reject", async () => {
    currentUser = staff;
    mp.adminProjects.mockResolvedValue(page([queued]));
    mp.moderateProject.mockResolvedValue({ ...queued, status: "published" });
    renderAt("/admin/marketplace");
    expect(await screen.findByRole("heading", { name: /Queued Kit/ })).toBeInTheDocument();
    expect(screen.getByText(/2 files left out by the upload check/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Approve and publish" }));
    await waitFor(() => expect(mp.moderateProject).toHaveBeenCalledWith(8, "approve", undefined));
    mp.moderateProject.mockRejectedValueOnce(err("x", { note: ["Tell the seller what to fix."] }));
    fireEvent.click(screen.getByRole("button", { name: "Reject…" }));
    fireEvent.click(screen.getByRole("button", { name: "Send rejection" }));
    expect(await screen.findByText("Tell the seller what to fix.")).toBeInTheDocument();
  });
});
