"""SQLite-backed operation history for MoveAny.

Records every operation run (copy / verify / repair / delete / list-batches)
with timestamps and result summary. Uses the standard library `sqlite3`, so no
extra dependency is required.
"""

import os
import sqlite3
import time

DB_FILENAME = ".moveany/moveany.db"


def _default_db_path():
    home = os.path.expanduser("~")
    return os.path.join(home, DB_FILENAME)


class OperationLog:
    """Append-only log of MoveAny operations, backed by SQLite."""

    def __init__(self, db_path=None):
        self.db_path = db_path or _default_db_path()
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._conn = sqlite3.connect(self.db_path)
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._init_schema()

    def _init_schema(self):
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS operations (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                op          TEXT NOT NULL,
                src_root    TEXT,
                dest_root   TEXT,
                batch       TEXT,
                started_at  REAL NOT NULL,
                finished_at REAL,
                summary     TEXT,
                status      TEXT
            );
            """
        )
        self._conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_operations_op ON operations(op);
            """
        )
        self._conn.commit()

    def start(self, op, src_root=None, dest_root=None, batch=None):
        """Open a new operation record, return its row id."""
        cur = self._conn.execute(
            "INSERT INTO operations (op, src_root, dest_root, batch, started_at, status)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (op, src_root, dest_root, batch, time.time(), "running"),
        )
        self._conn.commit()
        return cur.lastrowid

    def finish(self, op_id, status, summary=None):
        """Close an operation record with a status and optional summary JSON."""
        self._conn.execute(
            "UPDATE operations SET finished_at=?, status=?, summary=? WHERE id=?",
            (time.time(), status, summary, op_id),
        )
        self._conn.commit()

    def recent(self, limit=20, op=None):
        """Return the most recent operations (optionally filtered by type)."""
        if op:
            rows = self._conn.execute(
                "SELECT id, op, src_root, dest_root, batch, status, "
                "       started_at, finished_at, summary"
                " FROM operations WHERE op=? ORDER BY id DESC LIMIT ?",
                (op, limit),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT id, op, src_root, dest_root, batch, status, "
                "       started_at, finished_at, summary"
                " FROM operations ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(zip(
            ["id", "op", "src_root", "dest_root", "batch", "status",
             "started_at", "finished_at", "summary"], row)) for row in rows]

    def close(self):
        self._conn.close()
