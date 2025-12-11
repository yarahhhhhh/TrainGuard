from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
from app.serializer import process_json

app = FastAPI(title="TrainGuard API", version="0.1.0")

class IngestRequest(BaseModel):
    data: Dict[str, Any]

@app.get("/")
def read_root():
    return {"message": "Welcome to TrainGuard API"}

@app.post("/ingest")
def ingest_data(request: IngestRequest):
    try:
        result = process_json(request.data)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
