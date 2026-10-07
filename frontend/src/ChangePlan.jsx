import { useEffect, useState } from "react";
import { api, post } from "../api";
import { money, fmtDate } from "../format";
import { Section, Badge } from "../ui";

// Name of the field the change-plan endpoints expect. If Swagger shows a different
// name for GET .../change-plan/preview, change it here.
const PARAM = "new_plan_id";

function Line({ label, children, strong }) {
  return (
    <div className={`flex justify-between py-1 text-sm ${strong ? "border-t pt-2 font-semibold" : ""}`}>
      <span className="text-gray-600">{label}</span>
      <span className="text-gray-900">{children}</span>
    </div>
  );
}

function Preview({ p }) {
  if (typeof p.net_cents !== "number") {
    return (
      <pre className="mt-3 max-h-60 overflow-auto rounded-lg bg-gray-50 p-3 text-xs">
        {JSON.stringify(p, null, 2)}
      </pre>
    );
  }
  const cur = p.currency ?? "usd";
  const outcome =
    p.net_cents > 0
      ? `The customer will be invoiced ${money(p.net_cents, cur)}.`
      : p.net_cents < 0
      ? `The customer gets a ${money(-p.net_cents, cur)} credit, used on their next invoice.`
      : "No money changes hands.";

  return (
    <div className="mt-4 rounded-xl border border-gray-200 p-4">
      <h3 className="mb-2 font-semibold text-gray-900">What will happen</h3>
      <Line label="Unused time on the current plan">
        {typeof p.unused_fraction === "number" ? `${Math.round(p.unused_fraction * 100)}%` : "-"}
      </Line>
      <Line label="Credit for the unused time">{money(p.credit_cents, cur)}</Line>
      <Line label="Charge for the new plan">{money(p.charge_cents, cur)}</Line>
      <Line label="Net" strong>{money(p.net_cents, cur)}</Line>
      <p className="mt-3 text-sm text-gray-700">{outcome}</p>
      {p.new_period_end && (
        <p className="mt-1 text-xs text-gray-500">New period ends {fmtDate(p.new_period_end)}.</p>
      )}
    </div>
  );
}

export default function ChangePlan() {
  const [subs, setSubs] = useState(null);
  const [plans, setPlans] = useState(null);
  const [subId, setSubId] = useState("");
  const [planId, setPlanId] = useState("");
  const [preview, setPreview] = useState(null);
  const [done, setDone] = useState(null);
  const [error, setError] = useState(null);
  const [busy, setBusy] = useState(false);

  function load() {
    return Promise.all([api("/subscriptions"), api("/plans")])
      .then(([s, p]) => {
        setSubs(s.filter((x) => x.status !== "canceled"));
        setPlans(p);
      })
      .catch((e) => setError(e.message));
  }

  useEffect(() => {
    load();
  }, []);

  const current = subs?.find((s) => String(s.id) === String(subId));
  const options = plans?.filter((p) => !current || p.id !== current.plan_id) ?? [];

  function reset() {
    setPreview(null);
    setDone(null);
    setError(null);
  }

  async function runPreview() {
    reset();
    setBusy(true);
    try {
      setPreview(await api(`/subscriptions/${subId}/change-plan/preview?${PARAM}=${planId}`));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  async function apply() {
    if (!window.confirm(`Change subscription #${subId} to this plan? This cannot be undone.`)) return;
    setBusy(true);
    setError(null);
    try {
      const res = await post(`/subscriptions/${subId}/change-plan`, { [PARAM]: Number(planId) });
      setDone(res ?? { ok: true });
      setPreview(null);
      setPlanId("");
      await load();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  if (!subs || !plans) {
    return error ? (
      <p className="rounded-lg bg-red-50 p-4 text-red-700">Could not load: {error}</p>
    ) : (
      <p className="text-gray-500">Loading...</p>
    );
  }

  return (
    <Section
      title="Change a subscription's plan"
      subtitle="Preview the cost first. Nothing changes until you confirm."
    >
      <div className="flex flex-wrap items-end gap-3">
        <label className="text-sm text-gray-600">
          Subscription
          <select
            value={subId}
            onChange={(e) => { setSubId(e.target.value); setPlanId(""); reset(); }}
            className="mt-1 block rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-900"
          >
            <option value="">Choose...</option>
            {subs.map((s) => (
              <option key={s.id} value={s.id}>
                #{s.id} - {s.plan_name ?? `Plan ${s.plan_id}`} ({s.status})
              </option>
            ))}
          </select>
        </label>

        <label className="text-sm text-gray-600">
          New plan
          <select
            value={planId}
            onChange={(e) => { setPlanId(e.target.value); reset(); }}
            disabled={!subId}
            className="mt-1 block rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm text-gray-900 disabled:opacity-50"
          >
            <option value="">Choose...</option>
            {options.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name} - {money(p.amount_cents, p.currency)}/{p.interval}
              </option>
            ))}
          </select>
        </label>

        <button
          onClick={runPreview}
          disabled={!subId || !planId || busy}
          className="rounded-lg bg-indigo-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
        >
          {busy && !preview ? "Working..." : "Preview"}
        </button>
      </div>

      {error && <p className="mt-4 rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}

      {preview && (
        <>
          <Preview p={preview} />
          <button
            onClick={apply}
            disabled={busy}
            className="mt-4 rounded-lg bg-green-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-green-700 disabled:opacity-50"
          >
            {busy ? "Working..." : "Confirm change"}
          </button>
        </>
      )}

      {done && (
        <div className="mt-4 rounded-lg bg-green-50 p-3 text-sm text-green-800">
          <Badge text="done" style="bg-green-100 text-green-700" /> Plan changed. Check the
          Subscriptions and Invoices pages to see the result.
        </div>
      )}
    </Section>
  );
}