"""YouTube-Commons download and ingest into SQLite FTS5 index."""

import logging
import shutil
import sqlite3
import sys
from pathlib import Path

from yt_tts.config import Config
from yt_tts.exceptions import IndexError_

logger = logging.getLogger(__name__)

YOUTUBE_COMMONS_REPO = "Rijgersberg/YouTube-Commons"
TOTAL_PARQUET_FILES = 597  # train-00000-of-00597.parquet to train-00596-of-00597.parquet


def _check_disk_space(db_path: Path) -> None:
    """Warn if disk space is likely insufficient."""
    try:
        usage = shutil.disk_usage(db_path.parent)
        free_gb = usage.free / (1024**3)
        if free_gb < 60:
            print(
                f"WARNING: Only {free_gb:.1f} GB free disk space. "
                f"Full index may require 50-120 GB.",
                file=sys.stderr,
            )
    except OSError:
        pass


def _get_progress(conn: sqlite3.Connection) -> int:
    """Get the last completed Parquet file index."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS bootstrap_progress (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            last_completed_file INTEGER DEFAULT -1
        )
    """)
    row = conn.execute("SELECT last_completed_file FROM bootstrap_progress").fetchone()
    if row is None:
        conn.execute("INSERT INTO bootstrap_progress (id, last_completed_file) VALUES (1, -1)")
        conn.commit()
        return -1
    return row[0]


def _set_progress(conn: sqlite3.Connection, file_index: int) -> None:
    """Update the last completed Parquet file index."""
    conn.execute(
        "UPDATE bootstrap_progress SET last_completed_file = ?", (file_index,)
    )
    conn.commit()


def bootstrap_index(config: Config) -> None:
    """Download YouTube-Commons Parquet files and ingest into the transcript index.

    Uses huggingface_hub + pyarrow for lightweight deps.
    Streams row-group-by-row-group for memory efficiency.
    Resumable via progress tracking in SQLite.
    """
    try:
        from huggingface_hub import hf_hub_download
        import pyarrow.parquet as pq
    except ImportError:
        print(
            "Bootstrap requires extra dependencies. Install with:\n"
            "  pip install yt-tts[bootstrap]",
            file=sys.stderr,
        )
        raise SystemExit(1)

    try:
        from tqdm import tqdm
    except ImportError:
        tqdm = None

    from yt_tts.core.index import TranscriptIndex

    index = TranscriptIndex(config.db_path)
    _check_disk_space(config.db_path)

    num_files = config.bootstrap_subset or TOTAL_PARQUET_FILES
    num_files = min(num_files, TOTAL_PARQUET_FILES)

    # Get resume point
    conn = index._get_conn()
    last_completed = _get_progress(conn)
    start_file = last_completed + 1

    if start_file >= num_files:
        print("Bootstrap already complete.", file=sys.stderr)
        return

    if start_file > 0:
        print(f"Resuming from file {start_file}/{num_files}", file=sys.stderr)

    file_range = range(start_file, num_files)
    if tqdm:
        file_range = tqdm(file_range, desc="Parquet files", initial=start_file, total=num_files)

    for file_idx in file_range:
        filename = f"train-{file_idx:05d}-of-{TOTAL_PARQUET_FILES:05d}.parquet"

        try:
            # Download parquet file
            local_path = hf_hub_download(
                repo_id=YOUTUBE_COMMONS_REPO,
                filename=f"data/{filename}",
                repo_type="dataset",
            )

            # Read and process row groups
            pf = pq.ParquetFile(local_path)
            batch = []
            batch_size = 10_000

            for rg_idx in range(pf.metadata.num_row_groups):
                table = pf.read_row_group(rg_idx, columns=[
                    "video_id", "channel_id", "channel", "title",
                    "text", "original_language", "word_count",
                ])

                for row_idx in range(table.num_rows):
                    # Filter: English only
                    lang = table.column("original_language")[row_idx].as_py()
                    if lang != "en":
                        continue

                    record = {
                        "video_id": table.column("video_id")[row_idx].as_py(),
                        "channel_id": table.column("channel_id")[row_idx].as_py(),
                        "channel_name": table.column("channel")[row_idx].as_py(),
                        "title": table.column("title")[row_idx].as_py(),
                        "text": table.column("text")[row_idx].as_py(),
                        "language": "en",
                    }

                    batch.append(record)

                    if len(batch) >= batch_size:
                        index.bulk_insert(batch)
                        batch.clear()

            # Insert remaining
            if batch:
                index.bulk_insert(batch)
                batch.clear()

            _set_progress(conn, file_idx)

        except Exception as e:
            logger.error("Failed processing %s: %s", filename, e)
            raise IndexError_(f"Bootstrap failed at {filename}: {e}") from e

    # Optimize FTS after bulk load
    print("Optimizing FTS index...", file=sys.stderr)
    index.optimize()
    print("Bootstrap complete.", file=sys.stderr)
