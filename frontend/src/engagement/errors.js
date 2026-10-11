// One readable sentence for a failed like/comment request. 400 (spam filter, validation), 403 (not allowed,
// e.g. unverified email) and everything else use the server's own message (err.friendly); a 429 gets a plainer
// wording than DRF's "Expected available in N seconds".
export function engagementError(err) {
  if (err?.status === 429) return "You are doing that too often. Please wait a little and try again.";
  return err?.friendly || "Something went wrong. Please try again.";
}
