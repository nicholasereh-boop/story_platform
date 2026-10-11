// Start "Continue with Google". allauth requires a POST (with the CSRF token) to begin the login, so we submit a
// real HTML form: the browser then follows the redirects to Google and back (see README, "Starting Google login").
// The /accounts path is proxied to Django by Vite in development.
export function loginWithGoogle() {
  const csrf = document.cookie.split("; ").find((c) => c.startsWith("csrftoken="))?.split("=")[1] || "";
  const form = document.createElement("form");
  form.method = "POST";
  form.action = "/accounts/google/login/";
  for (const [name, value] of [["csrfmiddlewaretoken", csrf], ["process", "login"]]) {
    const input = document.createElement("input");
    input.type = "hidden";
    input.name = name;
    input.value = value;
    form.appendChild(input);
  }
  document.body.appendChild(form);
  form.submit();
}
