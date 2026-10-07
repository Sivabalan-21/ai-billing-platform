# AI Billing Platform

A subscription billing system with a React dashboard and four AI features.

**Live demo:** <your Vercel URL> (sign-in key required)

## What it does
- Plans, customers, subscriptions, invoices and payments (5 providers)
- Dunning (retries failed payments), usage billing, plan changes, trials
- Multi-currency, revenue recognition, daily scheduler, email log
- AI features: churn risk, payment failure prediction, customer lifetime value,
  and pricing suggestions explained by Claude

## Stack
FastAPI, SQLAlchemy, PostgreSQL (SQLite locally), scikit-learn, React, Vite,
Tailwind. Deployed on Render (backend, database) and Vercel (frontend).

## Run locally
Backend:
    cd backend
    python -m venv venv
    .\venv\Scripts\activate
    pip install -r requirements.txt
    copy .env.example .env      # then fill in your values
    uvicorn app.main:app --reload

Frontend:
    cd frontend
    npm install
    npm run dev                 # http://localhost:5173

If `ADMIN_API_KEY` is empty, the API has no protection. Set it for anything
that is publicly reachable.

## Honest notes about the AI features
- **Churn risk and payment failure** use models trained on synthetic data,
  because there is no real history yet. Treat the scores as demonstrations
  of the pipeline, not as measured predictions.
- **Customer lifetime value** is a plain formula (monthly revenue x expected
  lifetime), reusing the churn score. Lifetime is capped at 60 months.
- **Pricing suggestions** rest on an assumption: customers with higher churn
  risk react more strongly to price changes (sensitivity = 0.5 + 1.5 x average
  risk). There is no real price-change data. Suggestions are never applied
  automatically, and plans with fewer than 3 customers are marked
  "insufficient data".
- Claude only writes the plain-language explanation. It does not choose the
  numbers.

## Security
- One shared admin key (header `X-Admin-Key`). There are no per-user accounts
  and no audit trail yet.
- Use sandbox payment keys only until real authentication is added.

## Deployment notes
- Render's free tier sleeps when idle, so the first request can take up to a
  minute. The in-process scheduler is disabled there (`SCHEDULER_ENABLED=false`);
  run the daily job from the Actions page or an external cron.
- Set `CORS_ORIGINS` to the frontend URL and `VITE_API_URL` (Vercel) to the
  backend URL.

## Known limits
- Currency amounts assume two decimal places (zero-decimal currencies such as
  JPY will display wrongly).
- Plan change from the UI is not built yet.