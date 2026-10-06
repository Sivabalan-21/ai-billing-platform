import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { post } from "../actions";
import { money } from "../format";
import { Badge, Section, Table, Loading, STATUS_STYLE } from "../ui";

export default function Invoices() {
  const [rows, setRows] = useState(null);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState("all");
  const [msg, setMsg] = useState(null);

  const load = () =>
    api("/invoices").then(setRows).catch((e) => setError(e.message));

  useEffect(() => {
    load();
  }, []);

  const run = async (label, fn) => {
    setMsg(`${label}...`);
    try {
      const res = await fn();
      setMsg(`${label}: ${JSON.stringify(res)}`);
    } catch (e) {
      setMsg(`${label} failed: ${e.message}`);
    }
    load();
  };

  if (!rows) return <Loading error={error} />;

  const statuses = ["all", ...new Set(rows.map((r) => r.status))];
  const shown = filter === "all" ? rows : rows.filter((r) => r.status === filter);

  return (
    <Section title="Invoices" subtitle={`${shown.length} of ${rows.length} shown`}>
      <div className="mb-3 flex items-center gap-3">
        <select
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm"
        >
          {statuses.map((s) => (
            <option key={s} value={s}>{s.replaceAll("_", " ")}</option>
          ))}
        </select>
        <button
          onClick={() => run("Run billing", () => post("/billing/run"))}
          className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700"
        >
          Run billing
        </button>
      </div>
      {msg && <p className="mb-3 break-all rounded-lg bg-gray-50 p-3 text-xs text-gray-600">{msg}</p>}
      <Table
        head={["Invoice", "Subscription", "Amount", "Status", ""]}
        empty="No invoices match."
        rows={shown.map((i) => [
          `#${i.id}`,
          <Link key="l" to={`/subscriptions/${i.subscription_id}`} className="text-indigo-600 hover:underline">
            #{i.subscription_id}
          </Link>,
          money(i.amount_cents, i.currency ?? "usd"),
          <Badge key="b" text={i.status} style={STATUS_STYLE[i.status]} />,
          i.status !== "paid" && (
            <button
              key="p"
              onClick={() =>
                run(`Pay #${i.id}`, () =>
                  post(`/invoices/${i.id}/pay`, { payment_method: "pm_card_visa" })
                )
              }
              className="text-indigo-600 hover:underline"
            >
              Pay (test card)
            </button>
          ),
        ])}
      />
    </Section>
  );
}