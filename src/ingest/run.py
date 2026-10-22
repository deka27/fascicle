"""Ingestion: PDF -> section-labelled, sentence-aligned chunks -> Chroma."""
import argparse
import json
import logging
import re
import shutil
import sys
import unicodedata
from pathlib import Path

from pypdf import PdfReader

from src.rag.store import CHROMA_DIR, collection

CHUNK_SIZE, OVERLAP = 1000, 200  # characters

SECTION_NAMES = (
    r"abstract|introduction|background|theory|methods?|materials and methods|results(?: and discussions?)?"
    r"|discussion(?: and conclusions?)?|conclusions?|acknowledge?ments?|references|bibliography|appendix(?: [a-z])?"
)
HEADING = re.compile(rf"(?:[IVX]+\.|\d+\.)?\s*({SECTION_NAMES})", re.I)  # whole line, e.g. "2. Methods", "I. INTRODUCTION"
SMALL_CAPS = re.compile(r"\b([A-Z]) (?=[A-Z]{2})")  # IEEE small caps extract as "I NTRODUCTION"
SKIP = re.compile(r"acknowledge?ments?|references|bibliography", re.I)
BOILERPLATE = re.compile(r"bioRxiv|downloaded from|IOPscience", re.I)  # per-page publisher footers
GLYPH = re.compile(r"/C(\d{2,3})")  # some PDFs encode characters as /C<ascii code>
SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")


def clean(line):
    line = unicodedata.normalize("NFKC", line)  # ligatures like "ﬁ" -> "fi"
    return GLYPH.sub(lambda m: chr(int(m.group(1))), line).strip()


def heading(line):
    """Section name if the line is a heading. Must start uppercase, so "methods." in body text doesn't count."""
    if line.isupper():
        line = SMALL_CAPS.sub(r"\1", line)
    m = HEADING.fullmatch(line)
    if not (m and m.group(1)[0].isupper()):
        return None
    return re.sub(r" [a-z]$", lambda c: c.group().upper(), m.group(1).capitalize())  # "APPENDIX A" -> "Appendix A"


def sections(pdf):
    """Yield (page, section, text) runs. Acknowledgements and references are dropped."""
    section = "Main text"  # text before the first recognised heading

    def flush(buf):
        text = re.sub(r"(?<=[a-z])- (?=[a-z])", "", " ".join(buf))  # re-join words hyphenated across lines
        return [] if SKIP.fullmatch(section) or not text else [(page_no, section, text)]

    for page_no, page in enumerate(PdfReader(pdf).pages, 1):
        buf = []
        for line in map(clean, (page.extract_text() or "").splitlines()):
            if not line or BOILERPLATE.search(line):
                continue
            if name := heading(line):
                yield from flush(buf)
                section, buf = name, []
            else:
                buf.append(line)
        yield from flush(buf)


def chunk(text, size=CHUNK_SIZE, overlap=OVERLAP):
    """Pack whole sentences into chunks of <= size chars, repeating trailing sentences (<= overlap chars) in the next."""
    sentences = [s[i : i + size] for s in SENTENCE.split(text) for i in range(0, len(s), size)]
    chunks, cur = [], []
    for s in sentences:
        if cur and len(" ".join(cur)) + 1 + len(s) > size:
            chunks.append(" ".join(cur))
            while cur and (len(" ".join(cur)) > overlap or len(" ".join(cur)) + 1 + len(s) > size):
                cur.pop(0)
        cur.append(s)
    if cur:
        chunks.append(" ".join(cur))
    return chunks


def ingest(pdf, meta):
    ids, docs, metas = [], [], []
    for page, section, text in sections(pdf):
        for piece in chunk(text):
            ids.append(f"{pdf.stem}:{len(ids)}")
            docs.append(piece)
            metas.append({"source": pdf.name, "page": page, "section": section, **meta})
    if ids:
        collection().add(ids=ids, documents=docs, metadatas=metas)
    return metas


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--papers", type=Path, default=Path("papers/raw"))
    parser.add_argument("--manifest", type=Path, default=Path("papers/manifest.json"))
    args = parser.parse_args()
    logging.getLogger("pypdf").setLevel(logging.ERROR)  # font-encoding warnings on most scientific PDFs

    manifest = json.loads(args.manifest.read_text())
    pdfs = sorted(args.papers.glob("*.pdf"))
    if missing := [p.name for p in pdfs if p.name not in manifest]:
        sys.exit(f"Add these to {args.manifest} first (citations need title/authors/year): {missing}")

    shutil.rmtree(CHROMA_DIR, ignore_errors=True)  # full rebuild, so chunking changes never leave stale chunks
    for pdf in pdfs:
        metas = ingest(pdf, manifest[pdf.name])
        found = list(dict.fromkeys(m["section"] for m in metas))
        print(f"{pdf.name}: {len(metas)} chunks | {', '.join(found)}")
