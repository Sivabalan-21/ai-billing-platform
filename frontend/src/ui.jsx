import { money } from "./format";

export const LEVEL_STYLE = {
  high: "bg-red-100 text-red-700",
  medium: "bg-amber-100 text-amber-700",
  low: "bg-green-100 text-green-700",
};
export const ACTION_STYLE = {
  raise_price: "bg-green-100 text-green-700",
  lower_price: "bg-blue-100 text-blue-700",
  hold: "bg-gray-100 text-gray-700",
  insufficient_data: "bg-gray-100 text-gray-500",
};
export const STATUS_STYLE = {
  active: "bg-green-100 text-green-700",
  paid: "bg-green-100 text-green-700",
  past_due: "bg-amber-100 text-amber-700",
  open: "bg-amber-100 text-amber-700",
  failed: "bg-red-100 text-red-700",
  canceled: "bg-gray-100 text-gray-500",
  uncollectible: "bg-gray-100 text-gray-500",
};

export function Badge({ text, style = "bg-gray-100 text-gray-700" }) {
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${style}`}>
      {String(text).replaceAll("_", " ")}
    </span>
  );
}

export function Stat({ label, children, hint }) {
  return (
    <div className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-gray-200">
      <p className="text-sm text-gray-500">{label}</p>
      <div className="mt-1 text-2xl font-semibold text-gray-900">{children}</div>
      {hint && <p className="mt-1 text-xs text-gray-400">{hint}</p>}
    </div>
  );
}

export function Section({ title, subtitle, children }) {
  return (
    <section className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-gray-200">
      <h2 className="text-lg font-semibold text-gray-900">{title}</h2>
      {subtitle && <p className="mb-3 text-sm text-gray-500">{subtitle}</p>}
      <div className="overflow-x-auto">{children}</div>
    </section>
  );
}

export function Table({ head, rows, empty }) {
  if (!rows.length) return <p className="py-4 text-sm text-gray-400">{empty}</p>;
  return (
    <table className="w-full text-left text-sm">
      <thead>
        <tr className="border-b text-gray-500">
          {head.map((h) => (
            <th key={h} className="py-2 pr-4 font-medium">{h}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {rows.map((cells, i) => (
          <tr key={i} className="border-b last:border-0">
            {cells.map((c, j) => (
              <td key={j} className="py-2 pr-4">{c}</td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export function Totals({ totals }) {
  const entries = Object.entries(totals);
  if (!entries.length) return <span>-</span>;
  return entries.map(([cur, cents]) => <div key={cur}>{money(cents, cur)}</div>);
}

export function Loading({ error }) {
  if (error)
    return <p className="rounded-lg bg-red-50 p-4 text-red-700">Could not load: {error}</p>;
  return <p className="text-gray-500">Loading...</p>;
}