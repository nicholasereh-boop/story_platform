// Pure helpers for the Academy's browsing pages (catalog and My learning): course looks, sorting, and the playful bits
// (XP, levels, badges, greetings). No React here, so every rule is easy to test.

export const LEVELS = {
  beginner: { label: "Beginner", icon: "🌱", rank: 1 },
  intermediate: { label: "Intermediate", icon: "🚀", rank: 2 },
  advanced: { label: "Advanced", icon: "🔥", rank: 3 },
};

const EMOJI = [
  [/html/i, "🧱"], [/css|style|design|ui|ux/i, "🎨"], [/react|vue|svelte/i, "⚛️"], [/java|js|script|node|typescript/i, "⚡"],
  [/python|django|flask/i, "🐍"], [/sql|data|database/i, "🗄️"], [/git|github/i, "🌿"], [/api|backend|server|deploy/i, "🛠️"],
  [/seo|market|growth/i, "📈"], [/mobile|app/i, "📱"],
];
export function categoryEmoji(text) {
  const t = String(text || "");
  const hit = EMOJI.find(([re]) => re.test(t));
  return hit ? hit[1] : "🎓";
}

const PALETTES = [
  ["#1d2f63", "#3d2a7a", "#14634a"], ["#5a1f6b", "#243a8f", "#0e6b7a"], ["#7a3b12", "#6a1f4f", "#2b2f86"],
  ["#0e5a52", "#2d3f9a", "#6b2a8f"], ["#7a1f3d", "#3b2a86", "#0f6a5c"], ["#12527a", "#4b2a8f", "#2f7a3b"],
];
function hash(text) {
  let h = 0;
  for (const ch of String(text || "")) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  return h;
}
// The same course always gets the same colours, so the grid looks lively but stable.
export function gradientFor(seed) {
  const [a, b, c] = PALETTES[hash(seed) % PALETTES.length];
  return `linear-gradient(135deg, ${a}, ${b} 55%, ${c})`;
}

const DAY = 86_400_000;
export function isNew(course, now = Date.now()) {
  const t = Date.parse(course?.published_at);
  return Number.isFinite(t) && now - t >= 0 && now - t < 14 * DAY;
}

export const SORTS = [
  ["newest", "Newest first"], ["shortest", "Shortest first"], ["longest", "Longest first"], ["az", "A to Z"], ["price-low", "Price: low to high"],
];
export function sortCourses(items, how) {
  const list = [...items];
  const num = (v) => Number(v) || 0;
  switch (how) {
    case "shortest": return list.sort((a, b) => num(a.duration_seconds) - num(b.duration_seconds));
    case "longest": return list.sort((a, b) => num(b.duration_seconds) - num(a.duration_seconds));
    case "az": return list.sort((a, b) => String(a.title).localeCompare(String(b.title)));
    case "price-low": return list.sort((a, b) => num(a.price) - num(b.price));
    default: return list; // "newest": the server already sends newest first
  }
}

export function filterCourses(items, { level = "all", category = "all" } = {}) {
  return items.filter((c) => (level === "all" || c.level === level) && (category === "all" || c.category === category));
}

export const categoriesOf = (items) => [...new Set(items.map((c) => c.category).filter(Boolean))].sort((a, b) => a.localeCompare(b));

export function summarise(items) {
  const lessons = items.reduce((n, c) => n + (Number(c.lesson_count) || 0), 0);
  const seconds = items.reduce((n, c) => n + (Number(c.duration_seconds) || 0), 0);
  return { courses: items.length, lessons, hours: Math.round((seconds / 3600) * 10) / 10 };
}

// ---- My learning --------------------------------------------------------------------------------
export const isDone = (c) => Number(c.total) > 0 && Number(c.completed) >= Number(c.total);

export function greeting(date = new Date()) {
  const h = date.getHours();
  if (h < 5) return "Burning the midnight oil";
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}

export function firstName(user) {
  const raw = user?.display_name || user?.name || user?.first_name || String(user?.email || "").split("@")[0] || "";
  const word = String(raw).trim().split(/[\s._-]+/)[0] || "";
  return word ? word[0].toUpperCase() + word.slice(1) : "";
}

// 10 XP for every finished lesson, plus 50 for every finished course.
export function xpOf(items) {
  return items.reduce((xp, c) => xp + 10 * (Number(c.completed) || 0) + (isDone(c) ? 50 : 0), 0);
}

export const RANKS = ["Curious Cub", "Tag Tinkerer", "Style Slinger", "Script Sorcerer", "Bug Whisperer", "Full-stack Legend"];
export function levelOf(xp) {
  const safe = Math.max(0, Number(xp) || 0);
  const level = Math.floor(Math.sqrt(safe / 25)) + 1;
  const floor = 25 * (level - 1) ** 2;
  const next = 25 * level ** 2;
  return { level, xp: safe, into: safe - floor, span: next - floor, percent: Math.round((100 * (safe - floor)) / (next - floor)), rank: RANKS[Math.min(level - 1, RANKS.length - 1)] };
}

export function badgesOf(items, now = Date.now()) {
  const lessonsDone = items.reduce((n, c) => n + (Number(c.completed) || 0), 0);
  const recent = items.some((c) => { const t = Date.parse(c.last_activity); return Number.isFinite(t) && now - t < 3 * DAY; });
  return [
    { id: "first", icon: "👣", title: "First steps", hint: "Finish your first lesson", earned: lessonsDone >= 1 },
    { id: "half", icon: "⛰️", title: "Halfway hero", hint: "Get half way through a course", earned: items.some((c) => Number(c.percent) >= 50) },
    { id: "finisher", icon: "🏆", title: "Finisher", hint: "Complete a whole course", earned: items.some(isDone) },
    { id: "collector", icon: "📚", title: "Collector", hint: "Join three courses", earned: items.length >= 3 },
    { id: "fire", icon: "🔥", title: "On fire", hint: "Learn something in the last 3 days", earned: recent },
  ];
}

export function timeAgo(value, now = Date.now()) {
  const t = Date.parse(value);
  if (!Number.isFinite(t)) return "";
  const mins = Math.floor((now - t) / 60_000);
  if (mins < 2) return "just now";
  if (mins < 60) return `${mins} minutes ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return hours === 1 ? "1 hour ago" : `${hours} hours ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return days === 1 ? "yesterday" : `${days} days ago`;
  return "a while ago";
}

export const TIPS = [
  "Ten focused minutes a day beats a three-hour binge once a month.",
  "Type the code along with the video instead of just watching. Your fingers learn too.",
  "Stuck? Write your question in the lesson comments. Explaining it often solves it.",
  "Break it on purpose, then fix it. That is how bugs stop being scary.",
  "Finish one small project before starting the next course.",
  "Explain what you learned to a friend. If you can teach it, you own it.",
  "Take a short walk after a hard lesson. Your brain keeps working while you rest.",
];
export const tipOfTheDay = (date = new Date()) => TIPS[Math.floor(date.getTime() / DAY) % TIPS.length];