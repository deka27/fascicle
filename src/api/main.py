import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from src.rag.answer import answer, retrieve, stream_answer
from src.rag.store import collection

UI = Path(__file__).parents[2] / "frontend" / "index.html"


@asynccontextmanager
async def lifespan(app):
    retrieve("warm-up")  # load the embedding model at startup instead of on the first question (~4s)
    yield


app = FastAPI(title="Fascicle", lifespan=lifespan)


class Query(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    k: int = Field(5, ge=1, le=20)


@app.get("/", include_in_schema=False)
def ui():
    return FileResponse(UI)


@app.get("/health")
def health():
    return {"status": "ok", "chunks": collection().count()}


@app.post("/query")
def query(q: Query):
    return answer(q.question, q.k)


@app.post("/stream")
def stream(q: Query):
    """Server-sent events: one {"sources": [...]} event, then {"token": "..."} events, or {"error": "..."}."""

    def events():
        try:
            for e in stream_answer(q.question, q.k):
                yield f"data: {json.dumps(e)}\n\n"
        except Exception:
            logging.exception("stream failed")
            yield f"data: {json.dumps({'error': 'Answer generation failed. Check the server logs.'})}\n\n"

    return StreamingResponse(events(), media_type="text/event-stream")
