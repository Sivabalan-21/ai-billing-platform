import { useEffect, useState } from "react";
import { api } from "../api";
import { money, fmtDate } from "../format";
import { Section, Stat, Table, Loading } from "../ui";

const isRows = (v) => Array.isArray(v) && v.length > 0 && typeof v[0] === "object";

function cell(col, value, row) {
  if (value == null) return "-";
  if (col.endsWith("_cents") && typeof value === "number")
    return money(value, (row.currency ?? "usd").toLowerCase());
  if (col.endsWith("_at") || col.endsWith("_date")) return fmtDate(value);
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

function RowsTable({ title, rows }) {
  const cols = Object.keys(rows[0]);
  return (
    <Section title={title}>
      <Table
        head={cols.map((c) => c.replaceAll("_", " "))}
        empty="No data."
        rows={rows.map((r) => cols.map((c) => cell(c, r[c], r)))}
      />
    </Section>
  );
}

export default function DataPage({ title, path }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    setData(null);
    api(path).then(setData).catch((e) => setError(e.message));
  }, [path]);

  if (!data) return <Loading error={error} />;

  if (Array.isArray(data))
    return isRows(data) ? (
      <RowsTable title={title} rows={data} />
    ) : (
      <Section title={title}><p className="text-sm text-gray-400">No data yet.</p></Section>
    );

  const entries = Object.entries(data);
  const scalars = entries.filter(([, v]) => typeof v !== "object" || v === null);
  const rest = entries.filter(([, v]) => typeof v === "object" && v !== null);

  return (
    <div className="space-y-6">
      {scalars.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {scalars.map(([k, v]) => (
            <Stat key={k} label={k.replaceAll("_", " ")}>
              {cell(k, v, data)}
            </Stat>
          ))}
        </div>
      )}
      {rest.map(([k, v]) =>
        isRows(v) ? (
          <RowsTable key={k} title={k.replaceAll("_", " ")} rows={v} />
        ) : (
          <Section key={k} title={k.replaceAll("_", " ")}>
            <pre className="text-xs text-gray-600">{JSON.stringify(v, null, 2)}</pre>
          </Section>
        )
      )}
    </div>
  );
}