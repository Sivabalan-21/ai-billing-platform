import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { fmtDate } from "../format";
import { Badge, Section, Table, Loading, STATUS_STYLE } from "../ui";

export default function Subscriptions() {
  const [rows, setRows] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    api("/subscriptions").then(setRows).catch((e) => setError(e.message));
  }, []);

  if (!rows) return <Loading error={error} />;

  return (
    <Section title="Subscriptions" subtitle="Click one to see churn risk, payment risk, value and invoices.">
      <Table
        head={["ID", "Customer", "Plan", "Status", "Renews / ends", ""]}
        empty="No subscriptions yet."
        rows={rows.map((s) => [
          `#${s.id}`,
          s.customer_id ?? "-",
          s.plan_name ?? `Plan ${s.plan_id}`,
          <Badge key="b" text={s.status} style={STATUS_STYLE[s.status]} />,
          fmtDate(s.current_period_end),
          <Link key="l" to={`/subscriptions/${s.id}`} className="text-indigo-600 hover:underline">
            Details
          </Link>,
        ])}
      />
    </Section>
  );
}