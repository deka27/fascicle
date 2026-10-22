import json

import chromadb
import pytest
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
from fastapi.testclient import TestClient

from src.api import main
from src.rag import answer as rag
from src.rag.store import EMBED_MODEL

DOCS = {
    "qball": "Q-ball imaging reconstructs the orientation distribution function with the Funk-Radon transform.",
    "csd": "Constrained spherical deconvolution imposes a non-negativity constraint on the fibre orientation distribution.",
    "fact": "FACT propagates streamlines continuously from voxel to voxel along the principal eigenvector.",
}


@pytest.fixture
def tiny_index(tmp_path, monkeypatch):
    """A 3-passage index with the real embedding model, standing in for the corpus (no PDFs in CI)."""
    col = chromadb.PersistentClient(path=str(tmp_path)).create_collection(
        "papers", embedding_function=SentenceTransformerEmbeddingFunction(model_name=EMBED_MODEL)
    )
    meta = {"page": 1, "section": "Methods", "authors": "A", "year": 2000, "journal": "J"}
    col.add(ids=list(DOCS), documents=list(DOCS.values()), metadatas=[{"source": f"{n}.pdf", "title": n, **meta} for n in DOCS])
    monkeypatch.setattr(rag, "collection", lambda: col)
    monkeypatch.setattr(main, "collection", lambda: col)
    return col


def test_retrieve_ranks_matching_passage_first(tiny_index):
    top = rag.retrieve("How does q-ball imaging reconstruct the ODF?", k=2)
    assert top[0]["source"] == "qball.pdf"
    assert top[0]["section"] == "Methods" and "Funk-Radon" in top[0]["text"]


def test_health_validation_and_ui(tiny_index):
    with TestClient(main.app) as client:  # also runs the startup warm-up against the tiny index
        assert client.get("/health").json() == {"status": "ok", "chunks": 3}
        assert client.post("/query", json={"question": ""}).status_code == 422
        assert client.post("/query", json={"question": "x", "k": 99}).status_code == 422
        assert "<title>Fascicle</title>" in client.get("/").text


def test_stream_reports_llm_failure(tiny_index, monkeypatch):
    def no_llm():
        raise RuntimeError("DEEPSEEK_API_KEY missing")

    monkeypatch.setattr(rag, "client", no_llm)
    with TestClient(main.app) as client:
        body = client.post("/stream", json={"question": "What is FACT?"}).text
    events = [json.loads(e.removeprefix("data: ")) for e in body.split("\n\n") if e]
    assert len(events[0]["sources"]) == 3
    assert events[-1] == {"error": "Answer generation failed. Check the server logs."}
