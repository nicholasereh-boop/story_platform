import { describe, expect, it } from "vitest";
import { render } from "@testing-library/react";
import ArticleBody from "../features/news/components/ArticleBody";

const html = (markup) => render(<ArticleBody html={markup} />).container;

describe("ArticleBody", () => {
  it("renders the allowed formatting", () => {
    const c = html("<h2>Head</h2><p>One <strong>two</strong> <em>three</em></p><ul><li>a</li><li>b</li></ul><blockquote>q</blockquote><hr><p>x<br>y</p>");
    expect(c.querySelector("h2").textContent).toBe("Head");
    expect(c.querySelector("strong").textContent).toBe("two");
    expect(c.querySelectorAll("li").length).toBe(2);
    expect(c.querySelector("blockquote")).toBeTruthy();
    expect(c.querySelector("hr")).toBeTruthy();
    expect(c.querySelector("p br")).toBeTruthy();
  });

  it("drops scripts, handlers, frames and images (the server removes them too; this is the second wall)", () => {
    const c = html('<p onclick="x()" style="color:red">Hi<script>window.__pwned = 1</script><iframe src="https://e.example"></iframe><img src="x" onerror="window.__pwned = 2"><svg onload="window.__pwned = 3"></svg></p>');
    expect(c.querySelector("script,iframe,img,svg")).toBeNull();
    expect(c.querySelector("p").getAttribute("onclick")).toBeNull();
    expect(c.querySelector("p").getAttribute("style")).toBeNull();
    expect(window.__pwned).toBeUndefined();
  });

  it("keeps only safe links and makes them open safely", () => {
    const c = html('<p><a href="https://ok.example/a" onmouseover="x()" target="_self">good</a> <a href="javascript:alert(1)">bad</a> <a href="data:text/html;base64,AAAA">worse</a> <a href="mailto:a@b.example">mail</a> <a href="/relative">rel</a></p>');
    const links = Array.from(c.querySelectorAll("a"));
    expect(links.map((a) => a.getAttribute("href"))).toEqual(["https://ok.example/a", "mailto:a@b.example"]);
    for (const a of links) {
      expect(a.getAttribute("rel")).toBe("nofollow noopener noreferrer");
      expect(a.getAttribute("target")).toBe("_blank");
      expect(a.getAttribute("onmouseover")).toBeNull();
    }
    expect(c.textContent).toContain("bad");   // the text of a refused link stays, only the link goes
    expect(c.textContent).toContain("rel");
  });

  it("keeps the text of unknown tags and copes with empty or broken input", () => {
    expect(html("<custom-tag>kept</custom-tag>").textContent).toBe("kept");
    expect(html("").textContent).toBe("");
    expect(html(null).textContent).toBe("");
    expect(html("<p>unclosed <b>bold").textContent).toBe("unclosed bold");
  });

  it("shows markup-looking text as text, never as elements", () => {
    const c = html("<p>&lt;script&gt;alert(1)&lt;/script&gt;</p>");
    expect(c.querySelector("script")).toBeNull();
    expect(c.textContent).toBe("<script>alert(1)</script>");
  });
});