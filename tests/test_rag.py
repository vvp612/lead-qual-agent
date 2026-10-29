from service.rag import Knowledge, _sanitize


def test_indexes_all_docs(knowledge_dir):
    assert Knowledge(knowledge_dir).count == 2


def test_refund_question_retrieves_refund_doc_first(knowledge_dir):
    kb = Knowledge(knowledge_dir)
    hits = kb.search("how do refunds work, how many days")
    assert hits and hits[0]["title"] == "Refund policy"


def test_context_block_is_prompt_ready(knowledge_dir):
    block = Knowledge(knowledge_dir).context_block("express shipping next day delivery")
    assert "Source: " in block and "Shipping" in block


def test_query_sanitising_neutralises_fts_operators():
    # FTS5 operators/quotes are stripped; only plain words survive, OR-joined.
    assert _sanitize('refund" OR "secret -- drop*') == "refund OR secret OR drop"


def test_empty_query_returns_nothing(knowledge_dir):
    assert Knowledge(knowledge_dir).search("!!! ???") == []
