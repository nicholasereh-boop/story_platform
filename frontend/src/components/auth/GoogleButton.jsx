import { useQuery } from "@tanstack/react-query";
import { providers } from "../../api";
import { loginWithGoogle } from "../../utils/google";

// "Continue with Google". Hidden unless the backend says Google sign-in is configured (GET /auth/providers/),
// so a site without Google credentials never shows a button that cannot work.
export default function GoogleButton({ label = "Continue with Google" }) {
  const { data } = useQuery({ queryKey: ["auth", "providers"], queryFn: providers, staleTime: Infinity, retry: false });
  if (!data?.google) return null;
  return (
    <button type="button" className="btn secondary block google-btn" onClick={loginWithGoogle}>
      {label}
    </button>
  );
}
