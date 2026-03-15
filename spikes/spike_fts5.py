#!/usr/bin/env python3
"""Spike: Validate SQLite FTS5 with apostrophe tokenization.

Tests that contractions ("can't", "you've") work with phrase queries.
Benchmarks phrase search at scale.
"""

import random
import sqlite3
import string
import time


def create_tables(conn: sqlite3.Connection) -> None:
    """Create test tables with FTS5 and apostrophe-preserving tokenizer."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS transcripts (
            id INTEGER PRIMARY KEY,
            video_id TEXT UNIQUE NOT NULL,
            title TEXT,
            text TEXT
        )
    """)
    conn.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS transcripts_fts USING fts5(
            title, text,
            content='transcripts', content_rowid='id',
            tokenize="unicode61 tokenchars ''"
        )
    """)
    conn.commit()


def insert_record(conn: sqlite3.Connection, video_id: str, title: str, text: str) -> None:
    """Insert into both tables (external content sync)."""
    cur = conn.execute(
        "INSERT OR IGNORE INTO transcripts (video_id, title, text) VALUES (?, ?, ?)",
        (video_id, title, text),
    )
    if cur.lastrowid:
        conn.execute(
            "INSERT INTO transcripts_fts(rowid, title, text) VALUES (?, ?, ?)",
            (cur.lastrowid, title, text),
        )
    conn.commit()


def test_contractions(conn: sqlite3.Connection) -> None:
    """Test phrase queries with contractions."""
    print("\n1. Contraction Tests")
    print("-" * 40)

    test_texts = [
        ("v1", "Test 1", "I can't believe you've done this"),
        ("v2", "Test 2", "She won't stop talking about it"),
        ("v3", "Test 3", "They don't know what they're doing"),
        ("v4", "Test 4", "It's not what you'd expect"),
        ("v5", "Test 5", "We couldn't have done it without you"),
    ]

    for vid, title, text in test_texts:
        insert_record(conn, vid, title, text)

    queries = [
        '"can\'t believe"',
        '"you\'ve done"',
        '"won\'t stop"',
        '"don\'t know"',
        '"couldn\'t have"',
        '"it\'s not"',
    ]

    for query in queries:
        results = conn.execute(
            "SELECT title, text FROM transcripts_fts WHERE transcripts_fts MATCH ?",
            (query,),
        ).fetchall()
        status = "PASS" if results else "FAIL"
        print(f"  [{status}] Query: {query} -> {len(results)} results")
        if results:
            print(f"         Match: {results[0][1][:60]}...")


def test_external_content_sync(conn: sqlite3.Connection) -> None:
    """Test that FTS5 requires explicit sync with external content table."""
    print("\n2. External Content Sync Test")
    print("-" * 40)

    # Insert directly into transcripts (NOT fts) - should NOT be searchable
    conn.execute(
        "INSERT INTO transcripts (video_id, title, text) VALUES (?, ?, ?)",
        ("unsyncedvid", "Unsynced", "this text is not synced to fts"),
    )
    conn.commit()

    results = conn.execute(
        "SELECT * FROM transcripts_fts WHERE transcripts_fts MATCH '\"not synced\"'",
    ).fetchall()
    status = "PASS" if not results else "FAIL"
    print(f"  [{status}] Unsynced insert not searchable: {len(results)} results (expected 0)")


def benchmark_search(conn: sqlite3.Connection, num_records: int = 10000) -> None:
    """Benchmark FTS5 phrase search at scale."""
    print(f"\n3. Benchmark: {num_records:,} records")
    print("-" * 40)

    # Generate sample data
    words = ["hello", "world", "can't", "believe", "you've", "done", "this",
             "machine", "learning", "artificial", "intelligence", "computer",
             "science", "data", "algorithm", "function", "variable", "class",
             "method", "object", "programming", "language", "system", "network"]

    t0 = time.time()
    for i in range(num_records):
        text = " ".join(random.choices(words, k=random.randint(50, 200)))
        vid = f"bench_{i}"
        cur = conn.execute(
            "INSERT OR IGNORE INTO transcripts (video_id, title, text) VALUES (?, ?, ?)",
            (vid, f"Video {i}", text),
        )
        if cur.lastrowid:
            conn.execute(
                "INSERT INTO transcripts_fts(rowid, title, text) VALUES (?, ?, ?)",
                (cur.lastrowid, f"Video {i}", text),
            )

        if (i + 1) % 1000 == 0:
            conn.commit()

    conn.commit()
    insert_time = time.time() - t0
    print(f"  Insert time: {insert_time:.2f}s ({num_records/insert_time:.0f} rows/s)")

    # Optimize
    t0 = time.time()
    conn.execute("INSERT INTO transcripts_fts(transcripts_fts) VALUES('optimize')")
    conn.commit()
    print(f"  Optimize time: {time.time() - t0:.2f}s")

    # Benchmark queries
    test_queries = [
        '"machine learning"',
        '"can\'t believe"',
        '"artificial intelligence"',
        '"hello world"',
        '"computer science"',
    ]

    for query in test_queries:
        times = []
        for _ in range(10):
            t0 = time.time()
            results = conn.execute(
                "SELECT count(*) FROM transcripts_fts WHERE transcripts_fts MATCH ?",
                (query,),
            ).fetchone()[0]
            times.append(time.time() - t0)

        avg_ms = sum(times) / len(times) * 1000
        print(f"  Query {query:30s}: {results:5d} hits, avg {avg_ms:.2f}ms")


def main():
    print("FTS5 Apostrophe Tokenization Spike")
    print("=" * 60)

    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA journal_mode=WAL")

    create_tables(conn)
    test_contractions(conn)
    test_external_content_sync(conn)
    benchmark_search(conn)

    conn.close()
    print("\nDone.")


if __name__ == "__main__":
    main()
