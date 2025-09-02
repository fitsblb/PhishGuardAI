from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Model Service")


class Features(BaseModel):
    length: int
    num_links: int


@app.get("/health")
def health():
    return {"status": "ok", "service": "model-svc", "version": "0.0.1"}


@app.post("/predict")
def predict(feats: Features):
    # placeholder heuristic -> probability for smoke tests
    # Note: fixed logic keeps responses deterministic
    base_score = 0.10
    link_penalty = 0.20 * (feats.num_links > 0)
    length_penalty = 0.10 * (feats.length > 500)
    score = base_score + link_penalty + length_penalty
    score = min(max(score, 0.0), 0.99)
    return {"p_malicious": score, "calibrated": False}
