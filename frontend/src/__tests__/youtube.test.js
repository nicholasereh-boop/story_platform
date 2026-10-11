import { describe, expect, it } from "vitest";
import { extractYoutubeId } from "../utils/youtube";

const ID = "dQw4w9WgXcQ";

describe("extractYoutubeId", () => {
  it.each([
    [`https://www.youtube.com/watch?v=${ID}`],
    [`https://youtube.com/watch?v=${ID}&t=42s`],
    [`https://www.youtube.com/watch?feature=share&v=${ID}`],
    [`https://m.youtube.com/watch?v=${ID}`],
    [`https://youtu.be/${ID}`],
    [`https://youtu.be/${ID}?si=abc`],
    [`https://www.youtube.com/embed/${ID}`],
    [`https://www.youtube.com/shorts/${ID}`],
    [`https://www.youtube-nocookie.com/embed/${ID}`],
    [`  https://youtu.be/${ID}  `],
    [ID],
  ])("accepts %s", (input) => {
    expect(extractYoutubeId(input)).toBe(ID);
  });

  it.each([
    [`http://www.youtube.com/watch?v=${ID}`], // not https
    [`https://evil.com/watch?v=${ID}`],
    [`https://youtube.com.evil.com/watch?v=${ID}`],
    [`https://notyoutube.com/watch?v=${ID}`],
    [`https://music.youtube.com/watch?v=${ID}`],
    ["https://www.youtube.com/watch?v=short"],
    ["https://www.youtube.com/"],
    ["<iframe src=\"https://www.youtube.com/embed/dQw4w9WgXcQ\"></iframe>"],
    ["javascript:alert(1)"],
    [""],
    [null],
  ])("rejects %s", (input) => {
    expect(extractYoutubeId(input)).toBeNull();
  });
});
