"""SQLite 存储层。

分两张事实表：

* ``raw``  —— 数据源原样落库，主键 ``(source, source_id)``，天然幂等，
  重复跑同一页不会产生重复行。这是「不重」的第一道保证。
* ``books`` —— 归一化 + 跨源聚类后的规范条目，一个 ``title_key`` 一行。

另外用 ``crawl_state`` 记录每个采集任务的水位线，支持任意中断后续跑。
"""

from __future__ import annotations

import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Iterator, Sequence

from . import config

SCHEMA = """
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;

CREATE TABLE IF NOT EXISTS raw (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    source      TEXT NOT NULL,
    source_id   TEXT NOT NULL,
    title_raw   TEXT NOT NULL,
    author_raw  TEXT,
    publisher   TEXT,
    pub_year    TEXT,
    isbn        TEXT,
    category    TEXT,
    url         TEXT,
    fetched_at  TEXT,
    UNIQUE(source, source_id)
);
CREATE INDEX IF NOT EXISTS idx_raw_source ON raw(source);
CREATE INDEX IF NOT EXISTS idx_raw_title  ON raw(title_raw);

CREATE TABLE IF NOT EXISTS crawl_state (
    source     TEXT NOT NULL,
    task_key   TEXT NOT NULL,
    done       INTEGER NOT NULL DEFAULT 0,
    pages      INTEGER NOT NULL DEFAULT 0,
    items      INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT,
    PRIMARY KEY (source, task_key)
);

CREATE TABLE IF NOT EXISTS books (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    title_key   TEXT NOT NULL UNIQUE,
    edition     TEXT,
    volume      TEXT,
    author      TEXT,
    publisher   TEXT,
    pub_year    TEXT,
    isbn        TEXT,
    category    TEXT,
    sources     TEXT,
    n_sources   INTEGER NOT NULL DEFAULT 1,
    aliases     TEXT,
    confidence  REAL NOT NULL DEFAULT 0.0
);
CREATE INDEX IF NOT EXISTS idx_books_key ON books(title_key);

CREATE TABLE IF NOT EXISTS members (
    book_id INTEGER NOT NULL,
    raw_id  INTEGER NOT NULL,
    PRIMARY KEY (book_id, raw_id)
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")


class Store:
    def __init__(self, path: Path | None = None) -> None:
        self.path = Path(path or config.DB_PATH)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(self.path, check_same_thread=False, timeout=30)
        self._conn.executescript(SCHEMA)
        self._conn.commit()

    # ------------------------------------------------------------ 写入

    def add_raw(self, rows: Sequence[dict]) -> int:
        """批量写入原始记录，返回新增行数（已存在的被忽略）。"""
        if not rows:
            return 0
        ts = _now()
        payload = [
            (
                r["source"], r["source_id"], r["title_raw"], r.get("author_raw", ""),
                r.get("publisher", ""), r.get("pub_year", ""), r.get("isbn", ""),
                r.get("category", ""), r.get("url", ""), ts,
            )
            for r in rows
            if r.get("title_raw")
        ]
        with self._lock:
            before = self._conn.total_changes
            self._conn.executemany(
                "INSERT OR IGNORE INTO raw"
                "(source, source_id, title_raw, author_raw, publisher, pub_year,"
                " isbn, category, url, fetched_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                payload,
            )
            self._conn.commit()
            return self._conn.total_changes - before

    @contextmanager
    def _tx(self):
        with self._lock:
            try:
                yield self._conn
                self._conn.commit()
            except Exception:
                self._conn.rollback()
                raise

    def replace_books(self, books: Iterable[dict], members: Iterable[tuple[int, int]]) -> None:
        """整体替换规范表（聚类是全量重算，分块写回）。"""
        with self._tx() as c:
            c.execute("DELETE FROM books")
            c.execute("DELETE FROM members")
        with self._tx() as c:
            c.executemany(
                "INSERT INTO books(title, title_key, edition, volume, author, publisher,"
                " pub_year, isbn, category, sources, n_sources, aliases, confidence)"
                " VALUES (:title,:title_key,:edition,:volume,:author,:publisher,"
                " :pub_year,:isbn,:category,:sources,:n_sources,:aliases,:confidence)",
                books,
            )
            c.executemany("INSERT OR IGNORE INTO members(book_id, raw_id) VALUES (?,?)", members)

    # ------------------------------------------------------------ 状态

    def set_state(self, source: str, task_key: str, **fields) -> None:
        cols = ", ".join(f"{k}=?" for k in fields)
        with self._tx() as c:
            c.execute(
                "INSERT INTO crawl_state(source, task_key, updated_at) VALUES (?,?,?)"
                " ON CONFLICT(source, task_key) DO NOTHING",
                (source, task_key, _now()),
            )
            c.execute(
                f"UPDATE crawl_state SET {cols}, updated_at=? WHERE source=? AND task_key=?",
                (*fields.values(), _now(), source, task_key),
            )

    def get_state(self, source: str, task_key: str) -> dict:
        cur = self._conn.execute(
            "SELECT done, pages, items FROM crawl_state WHERE source=? AND task_key=?",
            (source, task_key),
        )
        row = cur.fetchone()
        return {"done": row[0], "pages": row[1], "items": row[2]} if row else {
            "done": 0, "pages": 0, "items": 0
        }

    # ------------------------------------------------------------ 读取

    def iter_raw(self, source: str | None = None, batch: int = 20000) -> Iterator[list[tuple]]:
        sql = "SELECT id, source, source_id, title_raw, author_raw, publisher, pub_year, isbn, category FROM raw"
        args: tuple = ()
        if source:
            sql += " WHERE source=?"
            args = (source,)
        cur = self._conn.execute(sql, args)
        while True:
            rows = cur.fetchmany(batch)
            if not rows:
                break
            yield rows

    def count(self, table: str) -> int:
        return self._conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]

    def source_breakdown(self) -> list[tuple[str, int, int]]:
        return list(
            self._conn.execute(
                "SELECT source, COUNT(*), COUNT(DISTINCT title_raw) FROM raw GROUP BY source ORDER BY 2 DESC"
            )
        )

    def close(self) -> None:
        self._conn.close()
