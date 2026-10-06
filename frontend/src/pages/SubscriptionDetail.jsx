import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import { money, fmtDate } from "../format";
import { Badge, Section, Stat, Table, Loading, LEVEL_STYLE, STATUS_STYLE } from "../ui";
import { post } from "../actions";
import ChangePlan from "../ChangePlan";

export default function SubscriptionDetail() {
  const { id } = useParams();
  const [data, setData] = useState(null);
  const [invoices, setInvoices] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    setData(null);
    Promise.all([api(`/subscriptions/${id}/overview`), api("/invoices")])
      .then(([overview, allInvoices]) => {
        setData(overview);
        setInvoices(allInvoices.filter((i) => String(i.subscription_id) === String(id)));
      })
      .catch((e) => setError(e.message));
  }, [id]);

  if (!data) return <Loading error={error} />;

  const { churn, payment_risk: pay, clv } = data;
  const cur = clv?.currency ?? "usd";

  return (
    <div className="space-y-6">
      <div>
        <Link to="/subscriptions" className="text-sm text-indigo-600 hover:underline">
          &larr; All subscriptions
        </Link>
        <h2 className="mt-1 flex items-center gap-3 text-xl font-semibold text-gray-900">
          Subscription #{data.id}
          <Badge text={data.status} style={STATUS_STYLE[data.status]} />
        </h2>
        <p className="text-sm text-gray-500">
          Customer {data.customer_id ?? "-"} &middot; period ends {fmtDate(data.current_period_end)}
        </p>
        {data.status !== "canceled" && (
  <button
    onClick={async () => {
      if (!confirm("Cancel this subscription?")) return;
      try {
        await post(`/subscriptions/${data.id}/cancel`);
        window.location.reload();
      } catch (e) {
        alert(e.message);
      }
    }}
    className="mt-2 text-sm text-red-600 hover:underline"
  >
    Cancel subscription
  </button>
)}
      </div>

      <div className="grid gap-4 sm:grid-cols-3">
        <Stat label="Churn risk" hint="Chance this customer leaves">
          {churn?.error ? "-" : `${churn.risk_percent}%`}
        </Stat>
        <Stat
          label="Payment failure risk"
          hint={pay?.error ? pay.error : pay.advice}
        >
          {pay?.error ? "-" : (
            <span className="flex items-center gap-2">
              {pay.failure_risk_percent}%
              <Badge text={pay.level} style={LEVEL_STYLE[pay.level]} />
            </span>
          )}
        </Stat>
        <Stat
          label="Lifetime value"
          hint={clv?.error ? clv.error : `Paid ${money(clv.paid_to_date_cents, cur)} + expected ${money(clv.expected_future_revenue_cents, cur)}`}
        >
          {clv?.error ? "-" : money(clv.clv_cents, cur)}
        </Stat>
      </div>
      {data.status !== "canceled" && <ChangePlan subId={data.id} currentPlanId={data.plan_id} />}

      {Array.isArray(churn?.reasons) && churn.reasons.length > 0 && (
        <Section title="Why the churn score is what it is">
          <ul className="list-disc pl-5 text-sm text-gray-700">
            {churn.reasons.map((r, i) => (
              <li key={i}>{typeof r === "string" ? r : JSON.stringify(r)}</li>
            ))}
          </ul>
        </Section>
      )}

      <Section title="Invoices for this subscription">
        <Table
          head={["Invoice", "Amount", "Status"]}
          empty="No invoices yet."
          rows={invoices.map((i) => [
            `#${i.id}`,
            money(i.amount_cents, i.currency ?? cur),
            <Badge key="b" text={i.status} style={STATUS_STYLE[i.status]} />,
          ])}
        />
      </Section>
    </div>
    
  );
}