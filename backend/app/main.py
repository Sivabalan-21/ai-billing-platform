from contextlib import asynccontextmanager
from fastapi import FastAPI
from apscheduler.schedulers.background import BackgroundScheduler
from app.database import Base, engine, SessionLocal
from app import models  # noqa: F401
from app.routers import billing, invoices, dunning, usage, plan_changes, trials, revenue, jobs, providers
from app.services.billing import utcnow
from app.services.invoicing import generate_due_invoices
from app.scheduler import start_scheduler, stop_scheduler

scheduler = BackgroundScheduler()


def billing_job():
    db = SessionLocal()
    try:
        generate_due_invoices(db, utcnow())
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    scheduler.add_job(billing_job, "interval", minutes=60, id="billing", replace_existing=True)
    scheduler.start()
    yield
    scheduler.shutdown()


app = FastAPI(title="AI Billing Platform", lifespan=lifespan)
app.include_router(billing.router)
app.include_router(invoices.router)
app.include_router(dunning.router)
app.include_router(usage.router)
app.include_router(plan_changes.router)
app.include_router(trials.router)
app.include_router(revenue.router)
app.include_router(jobs.router)
app.include_router(providers.router)


@app.on_event("startup")
def _start_scheduler():
    start_scheduler()


@app.on_event("shutdown")
def _stop_scheduler():
    stop_scheduler()

@app.get("/health")
def health():
    return {"status": "ok"}