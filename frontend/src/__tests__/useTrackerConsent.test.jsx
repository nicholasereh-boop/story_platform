import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

const auth = { ready: true, isStaff: false };
vi.mock("../auth/AuthContext", () => ({ useAuth: () => auth }));
vi.mock("../analytics/tracker", async (importOriginal) => ({ ...(await importOriginal()), sendPageView: vi.fn() }));

import * as tracker from "../analytics/tracker";
import { useTracker } from "../analytics/useTracker";
import { OPT_OUT_KEY, sendPageView } from "../analytics/tracker";
import { clearConsent, writeConsent } from "../privacy/consent";
import { ConsentProvider, useConsent } from "../privacy/ConsentContext";

// A tiny page: the tracker plus buttons that make a consent choice, like the real banner does.
function Page({ mode, configReady = true, enabled = true }) {
  const consent = useConsent();
  useTracker({ configReady, mode, enabled, version: consent.version });
  return (
    <>
      <button onClick={consent.accept}>accept</button>
      <button onClick={consent.reject}>reject</button>
    </>
  );
}
const show = (props) => render(<MemoryRouter><ConsentProvider mode={props.mode}><Page {...props} /></ConsentProvider></MemoryRouter>);

beforeEach(() => {
  vi.clearAllMocks();
  auth.ready = true; auth.isStaff = false;
  window.localStorage.clear(); clearConsent();
  tracker.configureTracker({ mode: "notice", enabled: true });
});
afterEach(() => { delete navigator.doNotTrack; });

describe("tracking and consent modes", () => {
  it("notice: counts straight away (today's behaviour)", () => {
    show({ mode: "notice" });
    expect(sendPageView).toHaveBeenCalledTimes(1);
  });

  it("counts nothing until the server's consent mode is known", () => {
    const view = show({ mode: "opt_out", configReady: false });
    expect(sendPageView).not.toHaveBeenCalled();
    view.unmount();
  });

  it("opt_in: nothing before Accept, then the page the visitor is on is counted once", () => {
    show({ mode: "opt_in" });
    expect(sendPageView).not.toHaveBeenCalled();
    fireEvent.click(screen.getByText("accept"));
    expect(sendPageView).toHaveBeenCalledTimes(1);
  });

  it("opt_in: Reject keeps counting off", () => {
    show({ mode: "opt_in" });
    fireEvent.click(screen.getByText("reject"));
    expect(sendPageView).not.toHaveBeenCalled();
  });

  it("opt_out: counts until Reject, and a remembered Reject means no counting", () => {
    const view = show({ mode: "opt_out" });
    expect(sendPageView).toHaveBeenCalledTimes(1);
    view.unmount();
    vi.clearAllMocks();
    writeConsent("rejected");
    show({ mode: "opt_out" });
    expect(sendPageView).not.toHaveBeenCalled();
  });

  it("Do Not Track and the footer switch still win over an Accept", () => {
    Object.defineProperty(navigator, "doNotTrack", { value: "1", configurable: true });
    show({ mode: "opt_in" });
    fireEvent.click(screen.getByText("accept"));
    expect(sendPageView).not.toHaveBeenCalled();
    delete navigator.doNotTrack;
    window.localStorage.setItem(OPT_OUT_KEY, "1");
    fireEvent.click(screen.getByText("reject"));
    fireEvent.click(screen.getByText("accept"));
    expect(sendPageView).not.toHaveBeenCalled();
  });

  it("analytics switched off on the server: nothing is counted in any mode", () => {
    show({ mode: "notice", enabled: false });
    expect(sendPageView).not.toHaveBeenCalled();
  });
});
