from fastapi import FastAPI
from pydantic import BaseModel

from member1.pipeline import analyze_crisis


app = FastAPI(
    title="CrisisSense API",
    description="Crisis analysis API for CrisisSense",
    version="1.0"
)


class CrisisRequest(BaseModel):
    text: str


@app.get("/")
def home():
    return {
        "message": "CrisisSense API is running"
    }


@app.post("/analyze")
def analyze(request: CrisisRequest):

    result = analyze_crisis(request.text)

    return result