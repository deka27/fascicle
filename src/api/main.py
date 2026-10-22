import json

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from src.rag.answer import answer, stream_answer
from src.rag.store import collection

app = FastAPI(title="Fascicle")


class Query(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    k: int = Field(5, ge=1, le=20)


@app.get("/health")
def health():
    return {"status": "ok", "chunks": collection().count()}


@app.post("/query")
def query(q: Query):
    return answer(q.question, q.k)


@app.post("/stream")
def stream(q: Query):
    """Server-sent events: one {"sources": [...]} event, then {"token": "..."} events."""
    events = (f"data: {json.dumps(e)}\n\n" for e in stream_answer(q.question, q.k))
    return StreamingResponse(events, media_type="text/event-stream")
