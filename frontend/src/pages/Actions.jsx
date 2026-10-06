import { useState } from "react";
import { post } from "../api";
import { Section } from "../ui";

function ActionCard({ title, description, button, onRun, inputLabel, confirmText }) {
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  async function run() {
    if (inputLabel && !value.trim()) return setError(`Enter ${inputLabel} first.`);
    if (confirmText && !window.confirm(confirmText.replace("{id}", value))) return;
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      setResult(await onRun(value.trim()));
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-xl border border-gray-200 p-4">
      <h3 className="font-semibold text-gray-900">{title}</h3>
      <p className="mb-3 text-sm text-gray-500">{description}</p>
      <div className="flex flex-wrap items-center gap-2">
        {inputLabel && (
          <input
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder={inputLabel}
            className="w-40 rounded-lg border border-gray-300 px-3 py-1.5 text-sm"
          />
        )}
        <button
          onClick={run}
          disabled={busy}
          className="rounded-lg bg-indigo-600 px-4 py-1.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
        >
          {busy ? "Working..." : button}
        </button>
      </div>
      {error && <p className="mt-3 rounded-lg bg-red-50 p-3 text-sm text-red-700">{error}</p>}
      {result !== null && (
        <pre className="mt-3 max-h-60 overflow-auto rounded-lg bg-gray-50 p-3 text-xs text-gray-800">
          {JSON.stringify(result, null, 2)}
        </pre>
      )}
    </div>
  );
}

export default function Actions() {
  return (
    <Section
      title="Actions"
      subtitle="These change real data in the connected database. Use test data only."
    >
      <div className="grid gap-4 lg:grid-cols-2">
        <ActionCard
          title="Run billing"
          description="Creates invoices for subscriptions that are due."
          button="Run billing"
          confirmText="Run billing for all due subscriptions?"
          onRun={() => post("/billing/run")}
        />
        <ActionCard
          title="Run dunning"
          description="Retries failed payments that are due for another attempt."
          button="Run dunning"
          confirmText="Retry all failed payments that are due?"
          onRun={() => post("/dunning/run")}
        />
        <ActionCard
          title="Run daily job"
          description="Runs renewals, retries, trials and emails in one go."
          button="Run daily job"
          confirmText="Run the whole daily job now?"
          onRun={() => post("/jobs/run-daily")}
        />
        <ActionCard
          title="Pay an invoice"
          description="Attempts payment on one invoice."
          inputLabel="Invoice ID"
          button="Pay invoice"
          confirmText="Try to pay invoice #{id}?"
          onRun={(id) => post(`/invoices/${id}/pay`)}
        />
        <ActionCard
          title="Cancel a subscription"
          description="Cancels one subscription."
          inputLabel="Subscription ID"
          button="Cancel subscription"
          confirmText="Cancel subscription #{id}? This is hard to undo."
          onRun={(id) => post(`/subscriptions/${id}/cancel`)}
        />
      </div>
    </Section>
  );
}   