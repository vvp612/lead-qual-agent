"""Retrieval over the knowledge base using SQLite FTS5 (BM25-ranked snippets).

No vector store, no embed model — keyword retrieval is deterministic, offline and
plenty for a support/lead corpus of a few dozen docs. `index_documents` loads the
Markdown files into an in-memory FTS5 table; `snippets` returns top matches as a
prompt-ready context block. A `Knowledge` object bundles both for the service.
"""
from __future__ import annotations

import pathlib
import re
import sqlite3


def _sanitize(query: str) -> str:
    """Strip FTS5 operators so user text can't break MATCH (e.g. a stray `" OR "`)."""
    tokens = re.findall(r"[a-zA-Z0-9]+", query)
    words = [t for t in tokens if t.upper() not in {"AND", "OR", "NOT", "NEAR"}]
    return " OR ".join(words)  # OR-rank so a few good hits still surface


def _title_and_body(text: str, fallback: str) -> tuple[str, str]:
    match = re.match(r"#\s+(.+)\n", text)
    title = match.group(1).strip() if match else fallback
    body = text[match.end():] if match else text
    return title, body


class Knowledge:
    def __init__(self, docs_dir: str | pathlib.Path):
        # check_same_thread: the index is read-only after startup and FastAPI serves
        # sync endpoints from a thread pool; each query uses its own cursor.
        self.conn = sqlite3.connect(":memory:", check_same_thread=False)
        self.conn.execute("CREATE VIRTUAL TABLE docs USING fts5(title, body, tokenize='porter unicode61')")
        self.count = self._index(pathlib.Path(docs_dir))

    def _index(self, root: pathlib.Path) -> int:
        files = sorted(root.glob("*.md"))
        added = 0
        for path in files:
            title, body = _title_and_body(path.read_text(encoding="utf-8"), path.stem)
            self.conn.execute("INSERT INTO docs (title, body) VALUES (?, ?)", (title, body))
            added += 1
        self.conn.commit()
        return added

    def search(self, query: str, k: int = 3) -> list[dict]:
        match = _sanitize(query)
        if not match:
            return []
        rows = self.conn.execute(
            """SELECT title, snippet(docs, 1, '', '', ' … ', 20) AS s
               FROM docs WHERE docs MATCH ? ORDER BY rank LIMIT ?""",
            (match, k),
        ).fetchall()
        return [{"title": t, "snippet": re.sub(r"\s+", " ", s).strip()} for t, s in rows]

    def context_block(self, query: str, k: int = 2) -> str:
        """Prompt-ready grounding text (empty string when nothing matches)."""
        lines = [f'- Source: "{hit["title"]}" — {hit["snippet"]}' for hit in self.search(query, k)]
        return "\n".join(lines)
