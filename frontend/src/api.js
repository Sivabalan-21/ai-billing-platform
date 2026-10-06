const BASE = import.meta.env.VITE_API_URL || "/api";
export async function api(path) {
  const res = await fetch(BASE + path);
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new Error(data?.detail ?? res.statusText);
  return data;
}   

export async function post(path, body) {
  const res = await fetch(BASE + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  let data = null;
  try { data = await res.json(); } catch { /* empty body */ }
  if (!res.ok) {
    const d = data?.detail;
    throw new Error(d ? (typeof d === "string" ? d : JSON.stringify(d)) : `${res.status} ${res.statusText}`);
  }
  return data;
}