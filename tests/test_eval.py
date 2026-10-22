from src.eval.run import retrieval_scores


def test_retrieval_scores():
    sources = [{"source": s} for s in ["a.pdf", "b.pdf", "a.pdf", "c.pdf"]]
    assert retrieval_scores(sources, {"b.pdf"}) == {"hit_rate": 1.0, "precision": 0.25, "mrr": 0.5}
    assert retrieval_scores(sources, {"z.pdf"}) == {"hit_rate": 0.0, "precision": 0.0, "mrr": 0.0}
