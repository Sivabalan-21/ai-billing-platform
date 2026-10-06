import { useEffect, useState } from "react";
import { api } from "./api";
import { post } from "./actions";
import { money } from "./format";
import { Section } from "./ui";

export default function ChangePlan({ subId, currentPlanId }) {
  const [plans, setPlans] = useState([]);
  const [to, setTo] = useState("");
  const [preview, setPreview] = useState(null);
  const [msg, setMsg] = useState(null);

  useEffect(() => {
    api("/plans").then(setPlans).catch((e) => setMsg(e.message));
  }, []);

  const others = plans.filter((p) => p.id !== currentPlanId);

  const doPreview = async () => {
    setMsg(null);
    try {
      setPreview(await api(`/subscriptions/${subId}/change-plan/preview?new_plan_id=${to}`));
    } catch (e) {
      setPreview(null);
      setMsg(e.message);
    }
  };

  const confirmChange = async () => {
  try {
    const res = await post(`/subscriptions/${subId}/change-plan`, { new_plan_id: Number(to) });
    alert(res.message);
    window.location.reload();
  } catch (e) {
    setMsg(e.message);
  }
};

  const cur = (preview?.currency ?? "usd").toLowerCase();

  return (
    <Section title="Change plan" subtitle="Preview the proration before confirming.">
      <div className="flex items-center gap-3">
        <select
          value={to}
          onChange={(e) => { setTo(e.target.value); setPreview(null); }}
          className="rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm"
        >
          <option value="">Choose a plan</option>
          {others.map((p) => (
            <option key={p.id} value={p.id}>{p.name}</option>
          ))}
        </select>
        <button
          disabled={!to}
          onClick={doPreview}
          className="rounded-lg border border-indigo-600 px-3 py-1.5 text-sm font-medium text-indigo-600 disabled:opacity-40"
        >
          Preview
        </button>
        {preview && (
          <button
            onClick={confirmChange}
            className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700"
          >
            Confirm change
          </button>
        )}
      </div>
      {preview && (
        <div className="mt-3 text-sm text-gray-700">
          <p>Credit for unused time: {money(preview.credit_cents, cur)}</p>
          <p>Charge for new plan: {money(preview.charge_cents, cur)}</p>
          <p className="font-medium">
            {preview.net_cents < 0
              ? `Net credit to customer: ${money(-preview.net_cents, cur)}`
              : `Net amount due: ${money(preview.net_cents, cur)}`}
          </p>
        </div>
      )}
      {msg && <p className="mt-3 rounded-lg bg-red-50 p-3 text-xs text-red-700">{msg}</p>}
    </Section>
  );
}