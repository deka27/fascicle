from src.ingest.run import chunk, heading


def test_chunks_keep_whole_sentences_with_overlap():
    text = " ".join(f"Sentence number {i} is here." for i in range(100))
    pieces = chunk(text, size=200, overlap=60)
    assert all(len(p) <= 200 for p in pieces)
    assert all(p.startswith("Sentence") and p.endswith(".") for p in pieces)
    assert pieces[0].split(". ")[-1] in pieces[1]  # last sentence repeats in the next chunk
    assert "Sentence number 99 is here." in pieces[-1]


def test_overlong_sentence_is_split():
    assert [len(p) for p in chunk("x" * 2500, size=1000)] == [1000, 1000, 500]


def test_empty_text_has_no_chunks():
    assert chunk("") == []


def test_heading_detection():
    assert heading("2. Methods") == "Methods"
    assert heading("MATERIALS AND METHODS") == "Materials and methods"
    assert heading("I. I NTRODUCTION") == "Introduction"  # IEEE small caps
    assert heading("APPENDIX B") == "Appendix B"
    assert heading("methods.") is None
    assert heading("Methods 41, 239-254.") is None
    assert heading("Results from Single q-Shell") is None
