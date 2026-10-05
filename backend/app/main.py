from contextlib import asynccontextmanager
from fastapi import FastAPI
from apscheduler.schedulers.background import BackgroundScheduler
from app.database import Base, engine, SessionLocal
from app import models  # noqa: F401
from app.routers import billing, invoices
from app.services.billing import utcnow
from app.services.invoicing import generate_due_invoices

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


@app.get("/health")
def health():
    return {"status": "ok"}