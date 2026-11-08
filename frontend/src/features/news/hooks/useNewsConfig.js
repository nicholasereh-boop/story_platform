import { useQuery } from "@tanstack/react-query";
import { getNewsConfig } from "../api/news";

// The server's News switches and the copyright contact. Failure is not an error screen: pages just fall back to defaults.
export function useNewsConfig() {
  const q = useQuery({ queryKey: ["news", "config"], queryFn: getNewsConfig, staleTime: 10 * 60_000, retry: false });
  return q.data || { copyright_contact: "", comments: false };
}
