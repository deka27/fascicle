# Build stage: install dependencies into a venv and pre-download the embedding model.
FROM python:3.12-slim AS build

ENV PIP_NO_CACHE_DIR=1 HF_HOME=/opt/hf
RUN python -m venv /opt/venv
ENV PATH=/opt/venv/bin:$PATH

# CPU-only torch first; the default Linux wheel bundles CUDA and adds several GB
RUN pip install torch --index-url https://download.pytorch.org/whl/cpu
COPY requirements.txt .
RUN pip install -r requirements.txt

# Model name comes from store.py, so the image always ships the model the index was built with
COPY src/rag/store.py /tmp/store.py
RUN cd /tmp && python -c "from store import EMBED_MODEL; \
    from sentence_transformers import SentenceTransformer; SentenceTransformer(EMBED_MODEL)"


# Runtime stage: venv + model + app code only.
FROM python:3.12-slim

ENV PATH=/opt/venv/bin:$PATH HF_HOME=/opt/hf HF_HUB_OFFLINE=1 PYTHONUNBUFFERED=1
COPY --from=build /opt/venv /opt/venv
COPY --from=build /opt/hf /opt/hf

RUN useradd --create-home app
WORKDIR /app
COPY src/ src/
COPY frontend/ frontend/
RUN mkdir chroma && chown app chroma
USER app

# The index (chroma/) holds text from copyrighted papers, so it is mounted at run time, not baked in.
EXPOSE 8000
CMD ["sh", "-c", "exec uvicorn src.api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
