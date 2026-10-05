from fastapi import FastAPI

app = FastAPI(title="AI Billing Platform")

@app.get("/health")
def health():
    return {"status": "ok"}