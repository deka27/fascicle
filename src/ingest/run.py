"""Baseline ingestion: PDF -> per-page fixed-size chunks -> Chroma."""
import argparse
import logging
import unicodedata
from pathlib import Path

from pypdf import PdfReader

from src.rag.store import collection

CHUNK_SIZE, OVERLAP = 1000, 200  # characters


def chunk(text, size=CHUNK_SIZE, overlap=OVERLAP):
    step = size - overlap
    return [text[i : i + size] for i in range(0, max(len(text) - overlap, 1), step)]


def ingest(pdf):
    ids, docs, metas = [], [], []
    for page_no, page in enumerate(PdfReader(pdf).pages, 1):
        text = " ".join(unicodedata.normalize("NFKC", page.extract_text() or "").split())  # NFKC: ligatures like "ﬁ" -> "fi"
        if not text:
            continue
        for i, piece in enumerate(chunk(text)):
            ids.append(f"{pdf.stem}:{page_no}:{i}")
            docs.append(piece)
            metas.append({"source": pdf.name, "page": page_no})
    if ids:
        collection().upsert(ids=ids, documents=docs, metadatas=metas)
    return len(ids)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--papers", type=Path, default=Path("papers/raw"))
    args = parser.parse_args()
    logging.getLogger("pypdf").setLevel(logging.ERROR)  # font-encoding warnings on most scientific PDFs
    for pdf in sorted(args.papers.glob("*.pdf")):
        print(f"{pdf.name}: {ingest(pdf)} chunks")
