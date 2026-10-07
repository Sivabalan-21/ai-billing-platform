import { useEffect, useState } from "react";
import { api, getKey, setKey, clearKey } from "./api";

export default function AuthGate({ children }) {
  const [authed, setAuthed] = useState(Boolean(getKey()));
  const [value, setValue] = useState("");
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    const onAuth = () => setAuthed(false);
    window.addEventListener("auth-required", onAuth);
    return () => window.removeEventListener("auth-required", onAuth);
  }, []);

  async function submit(e) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setKey(value.trim());
    try {
      await api("/plans"); // any protected endpoint works as a check
      setValue("");
      setAuthed(true);
    } catch (err) {
      clearKey();
      setError(err.message === "Not signed in" ? "That key was not accepted." : err.message);
    } finally {
      setBusy(false);
    }
  }

  if (authed) return children;

  return (
    <div className="flex min-h-screen items-center justify-center bg-gray-50 p-6">
      <form
        onSubmit={submit}
        className="w-full max-w-sm space-y-4 rounded-xl bg-white p-6 shadow-sm ring-1 ring-gray-200"
      >
        <h1 className="text-lg font-bold text-gray-900">Billing admin</h1>
        <p className="text-sm text-gray-500">Enter the admin key to continue.</p>
        <input
          type="password"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="Admin key"
          autoFocus
          className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm"
        />
        {error && <p className="rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}
        <button
          type="submit"
          disabled={busy || !value.trim()}
          className="w-full rounded-lg bg-indigo-600 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
        >
          {busy ? "Checking..." : "Sign in"}
        </button>
      </form>
    </div>
  );
}   