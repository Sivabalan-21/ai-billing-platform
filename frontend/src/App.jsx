import { useEffect, useState } from "react";
import { api } from "./api";
import { money, sumByCurrency } from "./format";

const LEVEL_STYLE = {
  high: "bg-red-100 text-red-700",
  medium: "bg-amber-100 text-amber-700",
  low: "bg-green-100 text-green-700",
};
const ACTION_STYLE = {
  raise_price: "bg-green-100 text-green-700",
  lower_price: "bg-blue-100 text-blue-700",
  hold: "bg-gray-100 text-gray-700",
  insufficient_data: "bg-gray-100 text-gray-500",
};

function Badge({ text, style }) {
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${style}`}>
      {text.replace("_", " ")}
    </span>
  );
}

function Stat({ label, children, hint }) {
  return (
    <div className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-gray-200">
      <p className="text-sm text-gray-500">{label}</p>
      <div className="mt-1 text-2xl font-semibold text-gray-900">{children}</div>
      {hint && <p className="mt-1 text-xs text-gray-400">{hint}</p>}
    </div>
  );
}

function Section({ title, subtitle, children }) {
  return (
    <section className="rounded-xl bg-white p-5 shadow-sm ring-1 ring-gray-200">
      <h2 className="text-lg font-semibold text-gray-900">{title}</h2>
      {subtitle && <p className="mb-3 text-sm text-gray-500">{subtitle}</p>}
      <div className="overflow-x-auto">{children}</div>
    </section>
  );
}

function Table({ head, rows, empty }) {
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

function Totals({ totals }) {
  const entries = Object.entries(totals);
  if (!entries.length) return <span>-</span>;
  return entries.map(([cur, cents]) => <div key={cur}>{money(cents, cur)}</div>);
}

export default function App() {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    Promise.all([
      api("/ai/clv"),
      api("/ai/payment-risk"),
      api("/ai/pricing-suggestions?min_subs=1&explain_with_ai=false"),
    ])
      .then(([clv, risk, pricing]) => setData({ clv, risk, pricing }))
      .catch((e) => setError(e.message));
  }, []);

  if (error)
    return (
      <div className="p-8">
        <p className="rounded-lg bg-red-50 p-4 text-red-700">
          Could not load the dashboard: {error}. Is the backend running on port 8000?
        </p>
      </div>
    );
  if (!data) return <p className="p-8 text-gray-500">Loading...</p>;

  const { clv, risk, pricing } = data;
  const highRisk = risk.filter((r) => r.level === "high").length;

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="border-b bg-white px-8 py-4">
        <h1 className="text-xl font-bold text-gray-900">Billing dashboard</h1>
      </header>

      <main className="mx-auto max-w-6xl space-y-6 p-8">
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Stat label="Live subscriptions">{clv.length}</Stat>
          <Stat label="Monthly revenue">
            <Totals totals={sumByCurrency(clv, "monthly_revenue_cents")} />
          </Stat>
          <Stat label="Total customer value" hint="Paid so far plus expected future revenue">
            <Totals totals={sumByCurrency(clv, "clv_cents")} />
          </Stat>
          <Stat label="Charges at risk (next 7 days)" hint={`${highRisk} high risk`}>
            {risk.length}
          </Stat>
        </div>

        <Section
          title="Payments likely to fail"
          subtitle="Charges due in the next 7 days with at least a 30% chance of being declined."
        >
          <Table
            head={["Subscription", "Risk", "Level", "Charge in", "Advice"]}
            empty="Nothing needs attention right now."
            rows={risk.map((r) => [
              `#${r.subscription_id}`,
              `${r.failure_risk_percent}%`,
              <Badge key="b" text={r.level} style={LEVEL_STYLE[r.level]} />,
              `${r.next_charge_in_days} days`,
              r.advice,
            ])}
          />
        </Section>

        <Section
          title="Most valuable customers"
          subtitle="Ranked by lifetime value. Shorter expected lifetimes mean a higher chance of leaving."
        >
          <Table
            head={["Subscription", "Monthly", "Churn risk", "Expected lifetime", "Lifetime value"]}
            empty="No live subscriptions yet."
            rows={clv.slice(0, 10).map((c) => [
              `#${c.subscription_id}`,
              money(c.monthly_revenue_cents, c.currency),
              `${c.churn_risk_percent}%`,
              `${c.expected_lifetime_months} months`,
              money(c.clv_cents, c.currency),
            ])}
          />
        </Section>

        <Section title="Pricing suggestions" subtitle={pricing.assumption}>
          <Table
            head={["Plan", "Customers", "Monthly revenue", "Suggestion"]}
            empty="No plans yet."
            rows={pricing.plans.map((p) => [
              p.plan_name,
              p.customers,
              money(p.monthly_revenue_cents, p.currency),
              <span key="s" className="flex items-center gap-2">
                <Badge text={p.action} style={ACTION_STYLE[p.action]} />
                {p.change_percent !== 0 && `${p.change_percent > 0 ? "+" : ""}${p.change_percent}%`}
              </span>,
            ])}
          />
        </Section>
      </main>
    </div>
  );
}