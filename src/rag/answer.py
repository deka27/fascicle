import os
from functools import cache

from dotenv import load_dotenv
from openai import OpenAI

from src.rag.store import collection

load_dotenv()

MODEL = "deepseek-chat"
SYSTEM = (
    "You answer questions about diffusion MRI and tractography using only the numbered sources provided. "
    "Cite sources inline as [n]. If the sources do not contain the answer, say so instead of guessing."
)


@cache
def client():
    # DeepSeek's API is OpenAI-compatible
    return OpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com")


def retrieve(question, k=5):
    r = collection().query(query_texts=[question], n_results=k)
    return [{"text": doc, **meta} for doc, meta in zip(r["documents"][0], r["metadatas"][0])]


def answer(question, k=5):
    sources = retrieve(question, k)
    context = "\n\n".join(
        f"[{n}] ({s['source']}, p.{s['page']})\n{s['text']}" for n, s in enumerate(sources, 1)
    )
    response = client().chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"Sources:\n\n{context}\n\nQuestion: {question}"},
        ],
    )
    return {"answer": response.choices[0].message.content, "sources": sources}
