from fastapi import FastAPI

app = FastAPI(title="PhishGuard Gateway")


@app.get("/health")
def health():

    # Later: add readiness checks (e.g., downstream pings)
    return {"status": "ok", "service": "gateway", "version": "0.0.1"}
