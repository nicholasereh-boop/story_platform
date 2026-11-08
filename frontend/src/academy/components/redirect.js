// Sends the browser to Paystack's checkout page. A separate function so tests can replace it. Only https addresses are followed.
export function redirectTo(url) {
  if (typeof url === "string" && url.startsWith("https://")) window.location.assign(url);
}