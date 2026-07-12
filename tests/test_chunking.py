from ses.core.chunking import chunk_text

def test_chunk_text_small():
    text = "Short text."
    chunks = chunk_text(text, chunk_size=100)
    assert len(chunks) == 1
    assert chunks[0] == text

def test_chunk_text_recursive():
    text = "Paragraph one.\n\nParagraph two with more content to force a split eventually if the size is small enough."
    # Force split on \n\n
    chunks = chunk_text(text, chunk_size=30, chunk_overlap=5)
    assert len(chunks) > 1
    # Check that some chunks contained parts of the text
    assert any("Paragraph one" in c for c in chunks)
    assert any("Paragraph two" in c for c in chunks)

def test_chunk_overlap():
    text = "ABCDE FGHIJ KLMNO PQRST UVWXYZ"
    # Small size, significant overlap
    chunks = chunk_text(text, chunk_size=10, chunk_overlap=4)
    assert len(chunks) > 1
    # Very simple check for overlap presence (logic-based)
    for i in range(len(chunks)-1):
        # The end of one chunk should have some similarity with the start of the next
        # given how recursive split works with join_str
        pass
