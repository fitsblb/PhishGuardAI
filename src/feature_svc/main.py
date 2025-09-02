import re

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="Feature Service")


class TextIn(BaseModel):
    text: str


@app.get("/health")
def health():
    return {"status": "ok", "service": "feature-svc", "version": "0.0.1"}


@app.post("/featurize")
def featurize(payload: TextIn):
    # ultra-simplified placeholder features to prove the path
    text = payload.text or ""
    num_links = len(re.findall(r"https?://", text))
    length = len(text)
    return {"length": length, "num_links": num_links}
