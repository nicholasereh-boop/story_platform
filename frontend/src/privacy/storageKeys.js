// Every localStorage / sessionStorage key the app writes. The privacy page prints this table, and a test
// (privacyTables.test.js) scans the source so a new key cannot be added without being listed here.
// (Cookies are different: the server sets them, and the privacy page gets that table from /api/v1/privacy-policy/.)
export const STORAGE_KEYS = [
  { key: "sb.visitor-id", storage: "localStorage", purpose: "A random code for counting visitors. Only a scrambled (hashed) copy ever reaches the server.", duration: "Until you clear your browser data", necessary: false },
  { key: "sb.session-id", storage: "sessionStorage", purpose: "A random code that groups the pages of one visit.", duration: "Until you close the tab", necessary: false },
  { key: "sb.analytics-off", storage: "localStorage", purpose: "Remembers that you switched visitor counting off.", duration: "Until you switch it on again or clear your browser data", necessary: false },
  { key: "sb.consent", storage: "localStorage", purpose: "Remembers your answer in the privacy banner (only used when the site asks for consent).", duration: "6 months", necessary: false },
  { key: "sb.signup-prompt.quiet-until", storage: "localStorage", purpose: "Remembers that you closed the invitation to join, so it stays quiet.", duration: "14 days", necessary: false },
  { key: "sb.page-views", storage: "sessionStorage", purpose: "Counts pages viewed in this visit, to decide when to show the invitation to join. Never sent anywhere.", duration: "Until you close the tab", necessary: false },
  { key: "storyboard:draft:<story id>", storage: "sessionStorage", purpose: "Staff only: a copy of an unsaved story in the editor, as crash protection.", duration: "Until you close the tab", necessary: true },
];
