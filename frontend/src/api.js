const BASE = import.meta.env.VITE_API_URL || "/api";
const KEY = "adminKey";

export const getKey = () => sessionStorage.getItem(KEY) || "";
export const setKey = (k) => sessionStorage.setItem(KEY, k);
export const clearKey = () => sessionStorage.removeItem(KEY);

function withKey(headers = {}) {
  const k = getKey();
  return k ? { ...headers, "X-Admin-Key": k } : headers;
}

async function readError(res, path) {
  if (res.status === 401) {
    clearKey();
    window.dispatchEvent(new Event("auth-required"));
    return new Error("Not signed in");
  }
  let detail = null;
  try { detail = (await res.json())?.detail; } catch { /* empty body */ }
  if (detail) return new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  return new Error(`${res.status} ${res.statusText} on ${path}`);
}

export async function api(path) {
  const res = await fetch(BASE + path, { headers: withKey() });
  if (!res.ok) throw await readError(res, path);
  return res.json();
}

export async function post(path, body) {
  const res = await fetch(BASE + path, {
    method: "POST",
    headers: withKey({ "Content-Type": "application/json" }),
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw await readError(res, path);
  try { return await res.json(); } catch { return null; }
}