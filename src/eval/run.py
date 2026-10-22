"""Evaluate the RAG pipeline against eval/questions.jsonl and log the run to MLflow.

Retrieval metrics compare retrieved chunks with each question's labelled source papers (no LLM needed):
  hit_rate   share of questions with at least one chunk from a relevant paper
  precision  share of retrieved chunks that come from a relevant paper
  mrr        mean of 1/rank of the first relevant chunk

Answer metrics use DeepSeek as the judge:
  faithfulness  share of the answer's claims supported by the retrieved passages (Ragas)
  correctness   share of the reference answer's claims covered by the answer. Computed here, not with
                Ragas FactualCorrectness: its "recall" mode divides response-side true positives by
                reference-side misses, which scored a 4-of-5-claims answer as 0.0.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
from statistics import mean

import mlflow
from openai import AsyncOpenAI
from ragas.llms import llm_factory
from ragas.metrics.collections import Faithfulness

from src.ingest.run import CHUNK_SIZE, OVERLAP
from src.rag import answer as rag
from src.rag.store import EMBED_MODEL

JUDGE_MODEL = "deepseek-chat"  # fixed, so scores stay comparable when the answering model changes
CORRECTNESS_PROMPT = """Compare a candidate answer with a reference answer.
Split the reference answer into its distinct factual claims. For each claim, decide whether the candidate
answer states it or something equivalent. Extra information in the candidate does not matter.
Return JSON: {{"claims": [{{"claim": "...", "covered": true}}]}}

Reference answer:
{reference}

Candidate answer:
{answer}"""


def retrieval_scores(sources, relevant):
    hits = [s["source"] in relevant for s in sources]
    return {
        "hit_rate": float(any(hits)),
        "precision": sum(hits) / len(hits),
        "mrr": next((1 / rank for rank, hit in enumerate(hits, 1) if hit), 0.0),
    }


def correctness(reference, answer):
    response = rag.client().chat.completions.create(
        model=JUDGE_MODEL,
        response_format={"type": "json_object"},
        messages=[{"role": "user", "content": CORRECTNESS_PROMPT.format(reference=reference, answer=answer)}],
    )
    claims = json.loads(response.choices[0].message.content)["claims"]
    missed = [c["claim"] for c in claims if not c["covered"]]
    return {"correctness": 1 - len(missed) / len(claims), "missed": missed}


def judge_scores(faithfulness, q, out):
    scores = {}
    try:
        # judge against exactly what the model saw: citation header (authors, year, title, section) + passage
        contexts = [f"{rag.cite(s)}\n{s['text']}" for s in out["sources"]]
        scores["faithfulness"] = faithfulness.score(
            user_input=q["question"], response=out["answer"], retrieved_contexts=contexts
        ).value
    except Exception as e:  # noqa: BLE001 -- judge output occasionally fails to parse; skip that score, keep the run
        print(f"  faithfulness judge failed: {e!r}")
    try:
        scores |= correctness(q["reference"], out["answer"])
    except Exception as e:  # noqa: BLE001
        print(f"  correctness judge failed: {e!r}")
    return scores


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--questions", type=Path, default=Path("eval/questions.jsonl"))
    parser.add_argument("--k", type=int, default=5)
    parser.add_argument("--no-judge", action="store_true", help="retrieval metrics only: no LLM calls, runs in seconds")
    args = parser.parse_args()

    questions = [json.loads(line) for line in args.questions.read_text().splitlines() if line.strip()]
    faithfulness = None
    if not args.no_judge:
        client = AsyncOpenAI(api_key=os.environ["DEEPSEEK_API_KEY"], base_url="https://api.deepseek.com")
        # Ragas's default output limit truncates the claim list for longer answers (IncompleteOutputException)
        faithfulness = Faithfulness(llm=llm_factory(JUDGE_MODEL, client=client, max_tokens=8192))

    rows = []
    for q in questions:
        out = rag.answer(q["question"], args.k) if faithfulness else {"sources": rag.retrieve(q["question"], args.k)}
        row = {"question": q["question"], "retrieved": [s["source"] for s in out["sources"]]}
        row |= retrieval_scores(out["sources"], set(q["papers"]))
        if faithfulness:
            row |= {"answer": out["answer"]} | judge_scores(faithfulness, q, out)
        rows.append(row)
        scores = " ".join(f"{m}={row[m]:.2f}" for m in ("precision", "mrr", "faithfulness", "correctness") if m in row)
        print(f"{'HIT ' if row['hit_rate'] else 'MISS'} {scores}  {q['question'][:70]}")

    names = ["hit_rate", "precision", "mrr"] + (["faithfulness", "correctness"] if faithfulness else [])
    metrics = {m: mean(r[m] for r in rows if m in r) for m in names if any(m in r for r in rows)}

    mlflow.set_experiment("fascicle")
    with mlflow.start_run():
        mlflow.log_params({
            "k": args.k, "chunk_size": CHUNK_SIZE, "overlap": OVERLAP, "embed_model": EMBED_MODEL,
            "llm": rag.MODEL if faithfulness else "-", "judge": JUDGE_MODEL if faithfulness else "-",
            "prompt_sha": hashlib.sha256(rag.SYSTEM.encode()).hexdigest()[:8], "n_questions": len(rows),
        })
        mlflow.log_metrics(metrics)
        mlflow.log_dict(rows, "results.json")

    print("\n" + "  ".join(f"{m}={v:.3f}" for m, v in metrics.items()))


if __name__ == "__main__":
    main()
