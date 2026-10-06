import { useEffect, useState } from "react";
import { api } from "../api";
import { money } from "../format";
import { Badge, Stat, Section, Table, Totals, LEVEL_STYLE, ACTION_STYLE } from "../ui";

// Return the first field that exists on the object
const pick = (obj, ...keys) => {
  for (const k of keys) if (obj?.[k] != null) return obj[k];
  return null;
};

// Sum cents per currency -> { usd: 12345 }
const sumBy = (rows, getCents) =>
  rows.reduce((acc, r) => {
    const cur = pick(r, "currency") ?? "usd";
    acc[cur] = (acc[cur] ?? 0) + (getCents(r) ?? 0);
    return acc;
  }, {});

export default function Dashboard() {
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
      <p className="rounded-lg bg-red-50 p-4 text-red-700">
        Could not load the dashboard: {error}. Is the backend running on port 8000?
      </p>
    );
  if (!data) return <p className="text-gray-500">Loading...</p>;

  const { clv, risk, pricing } = data;
  const clvRows = Array.isArray(clv) ? clv : clv?.items ?? [];
  const riskRows = Array.isArray(risk) ? risk : risk?.items ?? [];
  const pricingRows = pricing?.plans ?? [];

  const highRisk = riskRows.filter((r) => r.level === "high").length;
  const totalValue = sumBy(clvRows, (r) => pick(r, "clv_cents"));
  const monthly = sumBy(clvRows, (r) =>
    pick(r, "monthly_cents", "monthly_amount_cents", "monthly_revenue_cents", "price_cents")
  );

  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Live subscriptions">{clvRows.length}</Stat>
        <Stat label="Monthly revenue">
          <Totals totals={monthly} />
        </Stat>
        <Stat label="Total customer value">
          <Totals totals={totalValue} />
        </Stat>
        <Stat label="Charges at risk" hint="Renewing soon with high failure risk">
          {riskRows.length}
          {highRisk > 0 && <span className="ml-2 text-sm text-red-600">{highRisk} high</span>}
        </Stat>
      </div>

      <Section title="Most valuable customers" subtitle="Ranked by lifetime value">
        <Table
  head={["Subscription", "Lifetime value", "Churn risk", "Expected lifetime"]}
  empty="No live subscriptions."
  rows={clvRows.map((r) => [
    `#${r.subscription_id}`,
    money(r.clv_cents, r.currency),
    `${r.churn_risk_percent}%`,
    `${r.expected_lifetime_months} months`,
  ])}
/>
      </Section>

      <Section title="Charges at risk" subtitle="Renewals likely to fail">
        <Table
          head={["Subscription", "Failure risk", "Level", "Advice"]}
          empty="No at-risk charges right now."
          rows={riskRows.map((r) => [
            `#${pick(r, "subscription_id", "id")}`,
            `${pick(r, "failure_risk_percent") ?? "-"}%`,
            <Badge key="b" text={r.level ?? "-"} style={LEVEL_STYLE[r.level]} />,
            r.advice ?? "-",
          ])}
        />
      </Section>

      <Section title="Pricing suggestions" subtitle={pricing?.assumption}>
  <Table
    head={["Plan", "Price", "Customers", "Suggestion", "Reason"]}
    empty="No pricing data."
    rows={pricingRows.map((p) => [
      p.plan_name,
      money(p.current_price_cents, p.currency) +
        (p.suggested_price_cents && p.suggested_price_cents !== p.current_price_cents
          ? ` → ${money(p.suggested_price_cents, p.currency)}`
          : ""),
      p.customers,
      <Badge key="b" text={p.action} style={ACTION_STYLE[p.action]} />,
      (p.reasoning ?? []).join(" "),
    ])}
  />
</Section>
    </div>
  );
}