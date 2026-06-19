# Fascicle

**A retrieval-augmented question-answering system over the tractography & diffusion-MRI literature.**

> *fascicle* (n.) — (1) a bundle of nerve fibers running together through the brain; (2) one installment of a work published in parts. A literature assistant for tractography earns both meanings.

Ask a question about diffusion MRI, fiber tracking, bundle segmentation, or microstructure modeling, and Fascicle retrieves the relevant passages from a curated corpus of papers and documentation, then answers **with citations back to the source**. Built locally first, then hardened into a deployed, monitored, continuously-integrated service.

---

## Why this project exists

Two reasons, and they're worth being honest about:

1. **It's a real ML system end-to-end.** RAG app → containerized API → cloud deployment → evaluation harness → monitoring → CI/CD. That single arc covers the three skills hiring managers screen for (LLM application engineering, MLOps, cloud) in one artifact instead of three disconnected tutorials.
2. **It's in a domain I actually know.** Building this over tractography literature means I can make informed chunking and retrieval choices, write a *correct* evaluation set (because I know the right answers), and defend every design decision in an interview. A generic "chat with PDF" demo can't do that. The domain is the differentiator.

The deliverable is not "I studied MLOps." It's "here is a deployed system, here are its evaluation numbers, here is the architecture, ask me anything about it."

---

## What it does

- Ingests a corpus of dMRI / tractography papers and documentation (PDFs + text).
- Chunks and embeds them into a searchable vector store.
- Answers natural-language questions using only retrieved context, with inline citations to the originating paper and section.
- Streams responses through a REST API.
- Measures its own answer quality (retrieval precision + faithfulness) against a hand-built evaluation set.
- Detects drift and quality regressions in production.
- Redeploys automatically on every merge to `main`.

---

## Architecture

```
                 ┌─────────────────────────────────────────────┐
                 │                INGESTION                      │
   papers/ ─────▶│  parse PDFs → section-aware chunk → embed     │
   (PDF, txt)    │             → store in vector DB              │
                 └───────────────────────┬─────────────────────┘
                                         │
                                         ▼
                              ┌────────────────────┐
                              │   Vector store      │
                              │   (Chroma, local)   │
                              └─────────┬──────────┘
                                         │ retrieve top-k
                                         ▼
   user query ──▶ FastAPI /query ──▶ Retriever ──▶ LLM (+ context) ──▶ answer + citations
                       │                                                      │
                       │                                          logged to MLflow
                       ▼                                                      │
                  /health, /stream                                           ▼
                                                              Eval harness (Ragas)
                                                              Monitoring (Evidently)
```

Everything left of the LLM call runs on your machine for free. Only the final deployed service touches the cloud.

---

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Language | Python 3.11 | Default for ML |
| RAG framework | LlamaIndex (or LangChain) | Handles chunking, retrieval, orchestration; pick one and commit |
| Embeddings | `sentence-transformers` locally, or an API embedding model | Local = free during dev |
| Vector store | Chroma | Runs locally, zero infra to start |
| LLM | Anthropic or OpenAI API | Swappable behind one interface |
| Serving | FastAPI | Async, streaming, clean API |
| Frontend | React (or Streamlit) | Turns the service into a demoable product; Streamlit = fast, React = more impressive |
| Experiment tracking | MLflow | Log prompts, params, eval metrics; model registry |
| Containerization | Docker | "Runs anywhere," reproducible |
| CI/CD | GitHub Actions | Lint, test, build, deploy on merge |
| Cloud | AWS (ECS) or Google Cloud Run | Final deployment only |
| Evaluation | Ragas | Retrieval precision, faithfulness |
| Monitoring | Evidently | Embedding drift, quality metrics |

> Rule: **one tool per job.** Do not evaluate alternatives mid-build. Survey later if ever.

---

## Knowledge source (the corpus)

Start small — ~10–15 documents is enough to build the whole pipeline. Expand later.

Suggested seed corpus (you know these better than anyone):
- DIPY documentation / tutorials
- Foundational tracking papers: deterministic (EuDX), probabilistic tracking, CSD / FOD-based tracking
- Bundle segmentation / RecoBundles, atlas-based approaches
- Microstructure models (DTI, NODDI, etc.) for context questions
- A couple of review / survey papers for broad-coverage questions

Organize as:
```
papers/
  raw/            # original PDFs
  processed/      # extracted text + metadata (title, authors, year, section)
  manifest.json   # list of docs with ids, used for citation lookup
```

**Domain note:** scientific PDFs are messy — equations, multi-column layouts, figure captions. Don't aim for perfect extraction. Strip to clean text, keep section labels (Abstract / Methods / Results) as metadata so retrieval and citations can reference them.

---

## Repository structure

```
fascicle/
├── README.md
├── pyproject.toml / requirements.txt
├── .env.example                # API keys (never commit real keys)
├── papers/                     # corpus (see above)
├── src/
│   ├── ingest/                 # parse, chunk, embed, load to vector store
│   ├── rag/                    # retriever + generation + citation assembly
│   ├── api/                    # FastAPI app (query, stream, health)
│   ├── eval/                   # Ragas harness + the question set
│   └── monitoring/             # Evidently drift checks
├── frontend/                   # web UI (React or Streamlit) that calls the API
├── eval/
│   └── questions.jsonl         # your hand-built Q → grounded-answer pairs
├── tests/                      # pytest
├── Dockerfile
├── .github/workflows/ci.yml    # GitHub Actions pipeline
└── notebooks/                  # scratch experiments (kept out of the deployed image)
```

---

## Build roadmap

Build in **thin end-to-end slices**. Get an ugly version working start-to-finish before improving any single layer. A deployed mediocre RAG beats a perfect local one you never shipped. Commit to GitHub from Phase 0 — the commit history is itself a signal to recruiters.

### Phase 0 — Repo skeleton *(½ day)*
- [ ] Create repo, virtualenv, `requirements.txt`, `.env.example`, this README
- [ ] First commit. Push.

### Phase 1 — Ugliest possible end-to-end RAG *(2–3 days)*
- [ ] Drop ~10 papers in `papers/raw/`
- [ ] Extract text → naive fixed-size chunks → embed → load into Chroma
- [ ] One retrieval call + one LLM call that answers from retrieved chunks
- [ ] Wrap it in a single FastAPI `/query` endpoint
- [ ] **Milestone: you can curl a question and get a grounded answer locally.** That's already a demo.

### Phase 2 — Make the retrieval actually good *(3–5 days)*
- [ ] Section-aware chunking + metadata (title, year, section)
- [ ] Citations in the response (which paper + section each claim came from)
- [ ] Add response streaming (SSE) and a `/health` endpoint
- [ ] Log experiments (chunk size, top-k, prompt variants) to MLflow
- [ ] *(Optional)* add an agent/tool layer if you want the "agent" claim — e.g., a tool that filters by year or author

### Phase 2.5 — Web UI (complete the product) *(2–3 days)*
Keep it deliberately thin. The ML substance is what gets you hired; the UI just makes it clickable.
- [ ] Single page: a question box → streamed answer with visible citations
- [ ] Show which papers/sections each answer drew from (this is the "wow" detail — it proves grounding)
- [ ] Call the FastAPI `/query` (or `/stream`) endpoint; handle loading + errors
- [ ] Streamlit if you want it done in an afternoon; React if you want it to double as full-stack signal
- [ ] **Milestone: someone can open a link, type a question, and watch a cited answer appear.** That's a product, not a script.

> Resist frontend rabbit-holing. A clean, simple UI with real eval numbers behind it beats a beautiful UI with weak retrieval.

### Phase 3 — Evaluation (your differentiator) *(2–3 days)*
- [ ] Hand-write ~20 question → grounded-answer pairs in `eval/questions.jsonl` (use your domain knowledge)
- [ ] Wire up Ragas: measure retrieval precision + answer faithfulness
- [ ] Record baseline numbers in MLflow; iterate retrieval to improve them
- [ ] **Milestone: you have real quality numbers to put in the README and say out loud in interviews.**

### Phase 4 — Containerize + CI *(1–2 days)*
- [ ] Write `Dockerfile` (multi-stage), run the whole app in a container locally
- [ ] `pytest` for ingestion + retrieval
- [ ] GitHub Actions: lint → test → build image on every push

### Phase 5 — Deploy + monitor *(2–3 days, cloud billing starts here)*
- [ ] Push image to a registry, deploy to Cloud Run / ECS
- [ ] Add Evidently drift monitoring on input embeddings + logged quality metrics
- [ ] Extend GitHub Actions to deploy on merge to `main`
- [ ] **Capture proof** (live URL, screenshots, metrics), then **tear the cloud resources down** so you stop paying

### Phase 6 — Package it like it matters *(1 day)*
- [ ] Finalize README: architecture diagram, eval numbers, screenshots
- [ ] 2-minute Loom walkthrough
- [ ] Pin the repo on your GitHub profile

---

## Getting started

```bash
git clone https://github.com/deka27/fascicle.git
cd fascicle
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # add your LLM API key

# ingest the corpus
python -m src.ingest.run --papers papers/raw

# run the API
uvicorn src.api.main:app --reload
```

## Usage

```bash
curl -X POST localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "How does probabilistic tracking differ from deterministic tracking?"}'
```

Returns an answer plus the source passages and papers it was drawn from.

## Evaluation

```bash
python -m src.eval.run --questions eval/questions.jsonl
```

Reports retrieval precision and answer faithfulness, logged to MLflow. Run it before and after retrieval changes to prove improvement.

---

## Skills this demonstrates (the resume mapping)

| Layer in this repo | Job-posting language it satisfies |
|---|---|
| RAG pipeline, embeddings, prompts | "LLM application development," "RAG," "prompt engineering" |
| FastAPI service, streaming | "model serving," "REST APIs," "production ML" |
| React/Streamlit frontend | "full-stack," "end-to-end ownership," "shipped product" |
| Docker + GitHub Actions | "containerization," "CI/CD," "MLOps" |
| Cloud deployment | "AWS/GCP," "deploying ML to production" |
| Ragas eval harness | "model evaluation," "eval frameworks" — the line most candidates can't check |
| Evidently monitoring | "monitoring," "drift detection," "observability" |

---

## Roadmap / future work

- Hybrid retrieval (BM25 + dense) and a reranker
- Multi-turn conversation memory
- Figure/table extraction for richer answers
- A thin web UI

## Notes

- Never commit API keys. `.env` stays gitignored.
- Keep cloud resources off except when actively deploying/demoing.
- This is a learning + portfolio project; respect the licenses of any papers in your corpus and don't redistribute copyrighted PDFs in a public repo (keep `papers/raw/` gitignored).