from fastapi import FastAPI
from pydantic import BaseModel, Field

from src.rag.answer import answer

app = FastAPI(title="Fascicle")


class Query(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    k: int = Field(5, ge=1, le=20)


@app.post("/query")
def query(q: Query):
    return answer(q.question, q.k)
