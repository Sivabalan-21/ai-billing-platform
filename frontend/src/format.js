export function money(cents, currency = "usd") {
  return new Intl.NumberFormat(undefined, {
    style: "currency",
    currency: currency.toUpperCase(),
  }).format(cents / 100);
}

// Adds up a field per currency, e.g. { usd: 12300, eur: 4500 }
export function sumByCurrency(rows, key) {
  const totals = {};
  for (const r of rows) {
    totals[r.currency] = (totals[r.currency] || 0) + r[key];
  }
  return totals;
}