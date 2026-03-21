"""SQLite FTS5 transcript index for full-text search."""

import os
import sqlite3
import threading
from pathlib import Path

from yt_tts.exceptions import IndexError_
from yt_tts.types import SearchResult

_SCHEMA_TRANSCRIPTS = """\
CREATE TABLE IF NOT EXISTS transcripts (
    id INTEGER PRIMARY KEY,
    video_id TEXT UNIQUE NOT NULL,
    channel_id TEXT,
    channel_name TEXT,
    title TEXT,
    text TEXT,
    language TEXT DEFAULT 'en',
    word_count INTEGER,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

_SCHEMA_FTS = """\
CREATE VIRTUAL TABLE IF NOT EXISTS transcripts_fts USING fts5(
    title, text,
    content='transcripts', content_rowid='id',
    tokenize="unicode61 tokenchars ''''"
);
"""


class TranscriptIndex:
    """SQLite FTS5-backed transcript index with thread-safe connections."""

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        # Initialize the database schema on the calling thread's connection.
        conn = self._get_conn()
        conn.executescript(_SCHEMA_TRANSCRIPTS)
        conn.execute(_SCHEMA_FTS)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.commit()

    def _get_conn(self) -> sqlite3.Connection:
        """Return a thread-local SQLite connection."""
        conn = getattr(self._local, "conn", None)
        if conn is None:
            conn = sqlite3.connect(str(self._db_path))
            conn.row_factory = sqlite3.Row
            self._local.conn = conn
        return conn

    def insert(
        self,
        video_id: str,
        channel_id: str | None,
        channel_name: str | None,
        title: str | None,
        text: str,
        language: str = "en",
    ) -> int:
        """Insert a transcript into both transcripts and transcripts_fts.

        Uses INSERT OR IGNORE so duplicate video_ids are silently skipped.
        Returns the rowid of the inserted row (or 0 if ignored).
        """
        word_count = len(text.split())
        conn = self._get_conn()
        try:
            cur = conn.execute(
                "INSERT OR IGNORE INTO transcripts "
                "(video_id, channel_id, channel_name, title, text, language, word_count) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (video_id, channel_id, channel_name, title, text, language, word_count),
            )
            rowid = cur.lastrowid
            if cur.rowcount > 0:
                conn.execute(
                    "INSERT INTO transcripts_fts (rowid, title, text) VALUES (?, ?, ?)",
                    (rowid, title or "", text),
                )
            conn.commit()
            return rowid if cur.rowcount > 0 else 0
        except sqlite3.Error as exc:
            conn.rollback()
            raise IndexError_(f"Failed to insert transcript for {video_id}: {exc}") from exc

    def bulk_insert(self, batch: list[dict]) -> int:
        """Insert multiple transcripts in a single transaction.

        Each dict must have keys: video_id, channel_id, channel_name, title, text.
        Optional key: language (defaults to 'en').
        Returns count of rows actually inserted.
        """
        conn = self._get_conn()
        inserted = 0
        try:
            for item in batch:
                text = item["text"]
                word_count = len(text.split())
                language = item.get("language", "en")
                title = item.get("title") or ""
                cur = conn.execute(
                    "INSERT OR IGNORE INTO transcripts "
                    "(video_id, channel_id, channel_name, title, text, language, word_count) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        item["video_id"],
                        item.get("channel_id"),
                        item.get("channel_name"),
                        item.get("title"),
                        text,
                        language,
                        word_count,
                    ),
                )
                if cur.rowcount > 0:
                    conn.execute(
                        "INSERT INTO transcripts_fts (rowid, title, text) VALUES (?, ?, ?)",
                        (cur.lastrowid, title, text),
                    )
                    inserted += 1
            conn.commit()
            return inserted
        except sqlite3.Error as exc:
            conn.rollback()
            raise IndexError_(f"Bulk insert failed: {exc}") from exc

    def delete(self, video_id: str) -> None:
        """Delete a transcript from both transcripts and transcripts_fts."""
        conn = self._get_conn()
        try:
            row = conn.execute(
                "SELECT id, title, text FROM transcripts WHERE video_id = ?",
                (video_id,),
            ).fetchone()
            if row is None:
                return
            conn.execute(
                "INSERT INTO transcripts_fts (transcripts_fts, rowid, title, text) "
                "VALUES ('delete', ?, ?, ?)",
                (row["id"], row["title"] or "", row["text"]),
            )
            conn.execute("DELETE FROM transcripts WHERE video_id = ?", (video_id,))
            conn.commit()
        except sqlite3.Error as exc:
            conn.rollback()
            raise IndexError_(f"Failed to delete transcript for {video_id}: {exc}") from exc

    def search(
        self,
        phrase: str,
        channel_id: str | None = None,
        limit: int = 20,
    ) -> list[SearchResult]:
        """Search transcripts using FTS5 phrase query.

        Returns results ranked by FTS5 rank score, post-filtered to verify
        the phrase appears as a substring (case-insensitive) in the text.
        """
        conn = self._get_conn()
        # Use FTS5 quoted phrase syntax for exact phrase matching.
        fts_query = f'"{phrase}"'
        try:
            # Filter to English transcripts at the SQL level — the index
            # contains transcripts in 7 languages (en/es/nl/ru/it/de/fr)
            # from YouTube-Commons, and only ~70% are English.
            if channel_id:
                rows = conn.execute(
                    "SELECT t.video_id, t.channel_id, t.channel_name, t.title, t.text, "
                    "f.rank AS rank_score "
                    "FROM transcripts_fts f "
                    "JOIN transcripts t ON t.id = f.rowid "
                    "WHERE transcripts_fts MATCH ? AND t.channel_id = ? "
                    "AND t.language LIKE 'en%' "
                    "ORDER BY f.rank "
                    "LIMIT ?",
                    (fts_query, channel_id, limit * 5),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT t.video_id, t.channel_id, t.channel_name, t.title, t.text, "
                    "f.rank AS rank_score "
                    "FROM transcripts_fts f "
                    "JOIN transcripts t ON t.id = f.rowid "
                    "WHERE transcripts_fts MATCH ? "
                    "AND t.language LIKE 'en%' "
                    "ORDER BY f.rank "
                    "LIMIT ?",
                    (fts_query, limit * 5),
                ).fetchall()
        except sqlite3.Error as exc:
            raise IndexError_(f"Search failed for phrase '{phrase}': {exc}") from exc

        # Post-filter: verify phrase is an actual substring (case-insensitive).
        phrase_lower = phrase.lower()
        results: list[SearchResult] = []
        for row in rows:
            text = row["text"]
            if phrase_lower not in text.lower():
                continue
            # Build context: ~50 chars before/after match.
            idx = text.lower().index(phrase_lower)
            start = max(0, idx - 50)
            end = min(len(text), idx + len(phrase) + 50)
            context = text[start:end]
            if start > 0:
                context = "..." + context
            if end < len(text):
                context = context + "..."

            results.append(
                SearchResult(
                    video_id=row["video_id"],
                    channel_id=row["channel_id"] or "",
                    channel_name=row["channel_name"] or "",
                    title=row["title"] or "",
                    matched_text=phrase,
                    context_text=context,
                    rank_score=row["rank_score"],
                    has_auto_captions=True,
                )
            )
            if len(results) >= limit:
                break

        return results

    def stats(self) -> dict:
        """Return index statistics.

        Keys: total_transcripts, total_words, unique_channels, db_size_mb.
        """
        conn = self._get_conn()
        total = conn.execute("SELECT COUNT(*) FROM transcripts").fetchone()[0]
        words = conn.execute("SELECT COALESCE(SUM(word_count), 0) FROM transcripts").fetchone()[0]
        channels = conn.execute(
            "SELECT COUNT(DISTINCT channel_id) FROM transcripts WHERE channel_id IS NOT NULL"
        ).fetchone()[0]

        db_size = 0.0
        try:
            db_size = round(os.path.getsize(str(self._db_path)) / (1024 * 1024), 2)
        except OSError:
            pass

        return {
            "total_transcripts": total,
            "total_words": words,
            "unique_channels": channels,
            "db_size_mb": db_size,
        }

    def optimize(self) -> None:
        """Run FTS5 optimize command to merge internal b-tree segments."""
        conn = self._get_conn()
        try:
            conn.execute("INSERT INTO transcripts_fts (transcripts_fts) VALUES ('optimize')")
            conn.commit()
        except sqlite3.Error as exc:
            raise IndexError_(f"FTS5 optimize failed: {exc}") from exc

    def rebuild_fts(self) -> None:
        """Drop and rebuild the FTS5 index from the transcripts table."""
        conn = self._get_conn()
        try:
            conn.execute("DROP TABLE IF EXISTS transcripts_fts")
            conn.execute(_SCHEMA_FTS)
            conn.execute(
                "INSERT INTO transcripts_fts (rowid, title, text) "
                "SELECT id, COALESCE(title, ''), text FROM transcripts"
            )
            conn.commit()
        except sqlite3.Error as exc:
            conn.rollback()
            raise IndexError_(f"FTS5 rebuild failed: {exc}") from exc

    def has_video(self, video_id: str) -> bool:
        """Check if a video is already in the index."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT 1 FROM transcripts WHERE video_id = ? LIMIT 1",
            (video_id,),
        ).fetchone()
        return row is not None
