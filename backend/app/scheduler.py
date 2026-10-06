from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from app.config import settings
from app.database import SessionLocal
from app.services.jobs import run_daily

scheduler = BackgroundScheduler(timezone="UTC")


def _job():
    db = SessionLocal()
    try:
        run_daily(db)
    finally:
        db.close()


def start_scheduler():
    if not settings.scheduler_enabled:
        return
    scheduler.add_job(_job, CronTrigger(hour=2, minute=0), id="daily", replace_existing=True)
    scheduler.start()


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)