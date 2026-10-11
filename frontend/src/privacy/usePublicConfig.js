import { useQuery } from "@tanstack/react-query";
import { getPublicConfig } from "../api/security";
import { cleanMode } from "./consent";

// The few site settings the browser needs first. While loading (or if the request fails) `loaded` is false and callers
// must NOT start analytics: a visitor must never be counted before we know which consent mode applies.
export function usePublicConfig() {
  const query = useQuery({ queryKey: ["public-config"], queryFn: getPublicConfig, staleTime: Infinity, retry: 1 });
  const cfg = query.data;
  return {
    loaded: Boolean(cfg),
    failed: query.isError,
    mode: cleanMode(cfg?.consent_mode),
    analyticsEnabled: cfg ? cfg.analytics_enabled !== false : false,
    contactEmail: cfg?.contact_email || "",
    siteName: cfg?.site_name || "",
  };
}
