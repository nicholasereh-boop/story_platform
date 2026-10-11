import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import * as API from "../api";
import { MFA_EVENT, ensureCsrf } from "../api/client";

const AuthContext = createContext(null);

// Holds the logged-in user. The session lives in an HttpOnly cookie managed by Django:
// no token, password or user data is ever written to localStorage or sessionStorage.
export function AuthProvider({ children }) {
  const queryClient = useQueryClient();
  const [user, setUser] = useState(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        await ensureCsrf(); // makes sure the csrftoken cookie exists before any POST
        const current = await API.me();
        if (alive) setUser(current);
      } catch {
        /* backend offline: stay logged out, the login page shows the error */
      } finally {
        if (alive) setReady(true);
      }
    })();
    return () => {
      alive = false;
    };
  }, []);

  // The server said 403 mfa_required / mfa_setup_required (for example the two-step proof expired): reload the user so the
  // admin guard shows the code prompt or the setup screen.
  useEffect(() => {
    const onNeeded = async () => {
      try {
        setUser(await API.me());
      } catch {
        /* keep the current user; the next request will tell */
      }
    };
    window.addEventListener(MFA_EVENT, onNeeded);
    return () => window.removeEventListener(MFA_EVENT, onNeeded);
  }, []);

  const value = useMemo(() => {
    // After the session changes (login, sign-up, logout) cached answers belong to the previous visitor.
    const startSession = (next) => {
      setUser(next);
      queryClient.clear();
      return next;
    };
    return {
      user,
      ready,
      isStaff: Boolean(user?.is_staff),
      login: async (email, password) => startSession(await API.login({ email, password })),
      // Sign-up never logs anybody in and never says whether the address was already taken (no account enumeration):
      // the answer is always "check your email". The person logs in afterwards.
      register: ({ email, password, display_name }) => API.register({ email, password, display_name }),
      // Reload the user from the server (after a two-step code, MFA setup or a security change).
      refreshUser: async () => {
        const current = await API.me();
        setUser(current);
        return current;
      },
      logout: async () => {
        try {
          await API.logout();
        } finally {
          startSession(null);
        }
      },
      requestPasswordReset: (email) => API.requestPasswordReset(email),
      resetPassword: ({ uid, token, password }) => API.resetPassword({ uid, token, password }),
      // Verifies with the key from the emailed link; if the visitor is logged in, their user is updated too.
      verifyEmail: async (key) => {
        const result = await API.verifyEmail(key);
        setUser((u) => (u ? { ...u, email_verified: true } : u));
        return result;
      },
      resendVerification: () => API.resendVerification(),
      updateProfile: async ({ display_name, bio }) => {
        const updated = await API.updateProfile({ display_name, bio });
        setUser(updated);
        return updated;
      },
    };
  }, [user, ready, queryClient]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export const useAuth = () => useContext(AuthContext);
