from src.ingest.run import chunk


def test_chunks_overlap_and_cover_text():
    text = "".join(str(i % 10) for i in range(2500))
    pieces = chunk(text, size=1000, overlap=200)
    assert [len(p) for p in pieces] == [1000, 1000, 900]
    assert pieces[0][-200:] == pieces[1][:200]
    assert pieces[-1].endswith(text[-100:])


def test_short_text_is_one_chunk():
    assert chunk("abc") == ["abc"]
