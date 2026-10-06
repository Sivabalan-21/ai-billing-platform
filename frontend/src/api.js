const BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export async function api(path) {
  const res = await fetch(BASE + path);
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new Error(data?.detail ?? res.statusText);
  return data;
}   