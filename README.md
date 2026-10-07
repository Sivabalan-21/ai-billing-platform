# AI Billing Platform

A subscription billing system with a React dashboard and four AI features.

**Live demo:** (https://ai-billing-platform.vercel.app) (an admin key is required to sign in)

## What it does

- Plans, customers, subscriptions, invoices and payments (five providers)
- Dunning (retries failed payments), usage billing, plan changes with proration, trials
- Multi-currency prices, revenue recognition, an email log
- A daily job that handles renewals, trial conversions, usage invoices and payment retries
- AI features: churn risk, payment failure prediction, customer lifetime value, and
  pricing suggestions explained in plain language by Claude

## Dashboard pages

Dashboard, Subscriptions (with per-customer detail), Invoices, Dunning, Revenue, Trials,
Emails, Actions (run billing, run dunning, pay an invoice, cancel a subscription) and
Change plan (preview the cost, then confirm).

## Stack

FastAPI, SQLAlchemy, PostgreSQL (SQLite locally), scikit-learn, React, Vite, Tailwind.
Backend and database on Render, frontend on Vercel, scheduled job and tests on GitHub Actions.

## Run locally

Backend:

    cd backend
    python -m venv venv
    .\venv\Scripts\activate
    pip install -r requirements.txt
    copy .env.example .env      # then fill in your own values
    uvicorn app.main:app --reload

Frontend:

    cd frontend
    npm install
    npm run dev                 # http://localhost:5173

If `ADMIN_API_KEY` is empty, the API has no protection. Always set it on anything that
other people can reach.

## Tests

    cd backend
    pip install -r requirements-dev.txt
    python -m pytest -v

The tests use an in-memory database and fake payment providers, so they need no keys and
never touch the network. GitHub Actions runs them, and builds the frontend, on every push.

## Honest notes about the AI features

- **Churn risk and payment failure** use models trained on synthetic data, because there
  is no real history yet. Treat the scores as demonstrations of the pipeline, not as
  measured predictions.
- **Customer lifetime value** is a plain formula (monthly revenue x expected lifetime),
  reusing the churn score. Lifetime is capped at 60 months.
- **Pricing suggestions** rest on an assumption: customers with higher churn risk react
  more strongly to price changes (sensitivity = 0.5 + 1.5 x average risk). There is no real
  price-change data. Suggestions are never applied automatically, and plans with fewer than
  3 customers are marked "insufficient data".
- Claude only writes the plain-language explanation. It does not choose the numbers.

## Security

- One shared admin key, sent as the `X-Admin-Key` header. Only `/health` is open. There are
  no per-user accounts and no audit trail.
- Use sandbox payment keys only until real authentication is added.
- Never commit `.env`. It is listed in `.gitignore`, and `.env.example` documents the names
  without any values.

## Deployment notes

- Render's free tier sleeps when idle, so the first request can take up to a minute.
- The in-process scheduler is off on Render (`SCHEDULER_ENABLED=false`). A GitHub Actions
  workflow calls `POST /jobs/run-daily` every day at 02:30 UTC, using the repository secrets
  `API_URL` and `ADMIN_API_KEY`. If you rotate the admin key, update both Render and GitHub.
- Set `CORS_ORIGINS` on Render to the frontend URL, and `VITE_API_URL` on Vercel to the
  backend URL.

## Known limits

- Currency amounts assume two decimal places, so zero-decimal currencies such as JPY will
  display wrongly.
- Changing a plan across currencies is not supported.
- Billing runs once a day, so a charge can land up to a day after it is due.