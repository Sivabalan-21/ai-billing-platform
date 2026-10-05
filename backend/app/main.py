from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.database import Base, engine
from app import models  # noqa: F401
from app.routers import billing


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(title="AI Billing Platform", lifespan=lifespan)
app.include_router(billing.router)


@app.get("/health")
def health():
    return {"status": "ok"}