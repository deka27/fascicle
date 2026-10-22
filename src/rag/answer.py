import os
from functools import cache

from dotenv import load_dotenv
from openai import OpenAI

from src.rag.store import collection

load_dotenv()

MODEL = "deepseek-chat"
SYSTEM = (
    "You answer questions about diffusion MRI and tractography using only the numbered sources provided. "
    "Cite sources inline as [n] after each claim. If the sources do not contain the answer, say so instead of guessing."
)


@cache
def client():
    # DeepSeek's API is OpenAI-compatible
    return OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com")


def retrieve(question, k=5):
    r = collection().query(query_texts=[question], n_results=k)
    return [{"text": doc, **meta} for doc, meta in zip(r["documents"][0], r["metadatas"][0])]


def cite(s):
    return f"{s['authors']} ({s['year']}), \"{s['title']}\", {s['section']}, p.{s['page']}"


def messages(question, sources):
    context = "\n\n".join(f"[{n}] {cite(s)}\n{s['text']}" for n, s in enumerate(sources, 1))
    return [
        {"role": "system", "content": SYSTEM},
        {"role": "user", "content": f"Sources:\n\n{context}\n\nQuestion: {question}"},
    ]


def answer(question, k=5):
    sources = retrieve(question, k)
    response = client().chat.completions.create(model=MODEL, messages=messages(question, sources))
    return {"answer": response.choices[0].message.content, "sources": sources}


def stream_answer(question, k=5):
    """Yield the sources first, then the answer token by token."""
    sources = retrieve(question, k)
    yield {"sources": sources}
    for part in client().chat.completions.create(model=MODEL, messages=messages(question, sources), stream=True):
        if part.choices and (token := part.choices[0].delta.content):
            yield {"token": token}
