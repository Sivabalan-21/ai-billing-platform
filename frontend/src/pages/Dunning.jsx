import { useEffect, useState } from "react";
import { api } from "../api";
import { post } from "../actions";
import { Section, Table, Loading } from "../ui";

export default function Dunning() {
  const [rows, setRows] = useState(null);
  const [error, setError] = useState(null);
  const [msg, setMsg] = useState(null);

  const load = () =>
    api("/dunning/queue")
      .then((d) => setRows(Array.isArray(d) ? d : d?.items ?? d?.queue ?? []))
      .catch((e) => setError(e.message));

  useEffect(() => {
    load();
  }, []);

  const runNow = async () => {
    try {
      setMsg(JSON.stringify(await post("/dunning/run")));
    } catch (e) {
      setMsg(`Failed: ${e.message}`);
    }
    load();
  };

  if (!rows) return <Loading error={error} />;

  const cols = rows.length ? Object.keys(rows[0]) : [];

  return (
    <Section title="Dunning queue" subtitle="Failed payments waiting for a retry">
      <button
        onClick={runNow}
        className="mb-3 rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700"
      >
        Run dunning now
      </button>
      {msg && <p className="mb-3 break-all rounded-lg bg-gray-50 p-3 text-xs text-gray-600">{msg}</p>}
      <Table
        head={cols}
        empty="Queue is empty."
        rows={rows.map((r) => cols.map((c) => String(r[c] ?? "-")))}
      />
    </Section>
  );
}