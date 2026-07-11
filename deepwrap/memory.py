from __future__ import annotations

import json
import sqlite3
import threading
import time
import uuid

from pathlib import Path
from typing import Any, Iterable

from deepwrap.function_calling import Tool


class MemoryStore:
    """Persistent, namespace-aware agent memory and session transcript store."""

    def __init__(self, path: str | Path, namespace: str = "default") -> None:
        self.path = Path(path).expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.namespace = namespace
        self._lock = threading.RLock()
        self._connection = sqlite3.connect(self.path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._initialize()

    def _initialize(self) -> None:
        with self._lock, self._connection:
            self._connection.executescript(
                """
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS memories (
                    id TEXT PRIMARY KEY,
                    namespace TEXT NOT NULL,
                    content TEXT NOT NULL,
                    tags TEXT NOT NULL DEFAULT '[]',
                    importance REAL NOT NULL DEFAULT 0.5,
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_memories_namespace
                    ON memories(namespace, updated_at DESC);
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    namespace TEXT NOT NULL,
                    model TEXT NOT NULL,
                    title TEXT,
                    summary TEXT NOT NULL DEFAULT '',
                    created_at REAL NOT NULL,
                    updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS turns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    FOREIGN KEY(session_id) REFERENCES sessions(id)
                );
                CREATE INDEX IF NOT EXISTS idx_turns_session
                    ON turns(session_id, id);
                """
            )
            try:
                self._connection.execute(
                    "CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(id UNINDEXED, namespace UNINDEXED, content, tags)"
                )
            except sqlite3.OperationalError:
                pass

    @staticmethod
    def _row(row: sqlite3.Row) -> dict[str, Any]:
        result = dict(row)
        if "tags" in result:
            result["tags"] = json.loads(result["tags"] or "[]")
        return result

    def remember(
        self,
        content: str,
        tags: Iterable[str] | None = None,
        importance: float = 0.5,
    ) -> dict[str, Any]:
        content = content.strip()
        if not content:
            raise ValueError("Memory content cannot be empty.")
        memory_id = f"mem_{uuid.uuid4().hex}"
        now = time.time()
        encoded_tags = json.dumps(list(tags or ()), ensure_ascii=False)
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT INTO memories VALUES (?, ?, ?, ?, ?, ?, ?)",
                (memory_id, self.namespace, content, encoded_tags, max(0.0, min(1.0, importance)), now, now),
            )
            try:
                self._connection.execute(
                    "INSERT INTO memories_fts(id, namespace, content, tags) VALUES (?, ?, ?, ?)",
                    (memory_id, self.namespace, content, encoded_tags),
                )
            except sqlite3.OperationalError:
                pass
        return self.get(memory_id)

    def get(self, memory_id: str) -> dict[str, Any]:
        with self._lock:
            row = self._connection.execute(
                "SELECT * FROM memories WHERE id = ? AND namespace = ?",
                (memory_id, self.namespace),
            ).fetchone()
        if row is None:
            raise ValueError(f"Unknown memory: {memory_id}")
        return self._row(row)

    def recall(self, query: str, limit: int = 8) -> list[dict[str, Any]]:
        query = query.strip()
        limit = max(1, min(limit, 50))
        with self._lock:
            try:
                rows = self._connection.execute(
                    """
                    SELECT m.*, bm25(memories_fts) AS lexical_score
                    FROM memories_fts
                    JOIN memories m ON m.id = memories_fts.id
                    WHERE memories_fts MATCH ? AND m.namespace = ?
                    ORDER BY lexical_score, m.importance DESC, m.updated_at DESC
                    LIMIT ?
                    """,
                    (query, self.namespace, limit),
                ).fetchall()
            except sqlite3.OperationalError:
                rows = self._connection.execute(
                    """
                    SELECT * FROM memories
                    WHERE namespace = ? AND content LIKE ?
                    ORDER BY importance DESC, updated_at DESC LIMIT ?
                    """,
                    (self.namespace, f"%{query}%", limit),
                ).fetchall()
        return [self._row(row) for row in rows]

    def list(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM memories WHERE namespace = ? ORDER BY updated_at DESC LIMIT ?",
                (self.namespace, max(1, min(limit, 500))),
            ).fetchall()
        return [self._row(row) for row in rows]

    def forget(self, memory_id: str) -> dict[str, Any]:
        memory = self.get(memory_id)
        with self._lock, self._connection:
            self._connection.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
            try:
                self._connection.execute("DELETE FROM memories_fts WHERE id = ?", (memory_id,))
            except sqlite3.OperationalError:
                pass
        return {"forgotten": memory_id, "content": memory["content"]}

    def create_session(self, model: str, title: str | None = None) -> str:
        session_id = f"session_{uuid.uuid4().hex}"
        now = time.time()
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT INTO sessions VALUES (?, ?, ?, ?, '', ?, ?)",
                (session_id, self.namespace, model, title, now, now),
            )
        return session_id

    def add_turn(self, session_id: str, role: str, content: str) -> None:
        now = time.time()
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT INTO turns(session_id, role, content, created_at) VALUES (?, ?, ?, ?)",
                (session_id, role, content, now),
            )
            self._connection.execute(
                "UPDATE sessions SET updated_at = ? WHERE id = ?",
                (now, session_id),
            )

    def session_context(self, session_id: str, limit: int = 20) -> str:
        with self._lock:
            session = self._connection.execute(
                "SELECT * FROM sessions WHERE id = ? AND namespace = ?",
                (session_id, self.namespace),
            ).fetchone()
            if session is None:
                raise ValueError(f"Unknown session: {session_id}")
            turns = self._connection.execute(
                "SELECT role, content FROM turns WHERE session_id = ? ORDER BY id DESC LIMIT ?",
                (session_id, max(1, min(limit, 100))),
            ).fetchall()[::-1]
        parts = [f"summary: {session['summary']}"] if session["summary"] else []
        parts.extend(f"{row['role']}: {row['content']}" for row in turns)
        return "\n".join(parts)

    def checkpoint(self, session_id: str, summary: str) -> dict[str, Any]:
        now = time.time()
        with self._lock, self._connection:
            cursor = self._connection.execute(
                "UPDATE sessions SET summary = ?, updated_at = ? WHERE id = ? AND namespace = ?",
                (summary, now, session_id, self.namespace),
            )
        if cursor.rowcount == 0:
            raise ValueError(f"Unknown session: {session_id}")
        return {"session_id": session_id, "summary": summary}

    def list_sessions(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT * FROM sessions WHERE namespace = ? ORDER BY updated_at DESC LIMIT ?",
                (self.namespace, max(1, min(limit, 100))),
            ).fetchall()
        return [dict(row) for row in rows]

    @property
    def definitions(self) -> tuple[Tool, ...]:
        return (
            Tool("remember", "Store information in durable long-term memory exactly as requested.", {"type": "object", "properties": {"content": {"type": "string"}, "tags": {"type": "array", "items": {"type": "string"}}, "importance": {"type": "number", "default": 0.5}}, "required": ["content"]}),
            Tool("recall", "Search durable memory for relevant information.", {"type": "object", "properties": {"query": {"type": "string"}, "limit": {"type": "integer", "default": 8}}, "required": ["query"]}),
            Tool("list_memories", "List recently stored long-term memories.", {"type": "object", "properties": {"limit": {"type": "integer", "default": 50}}}),
            Tool("forget", "Permanently remove a memory by ID.", {"type": "object", "properties": {"memory_id": {"type": "string"}}, "required": ["memory_id"]}),
            Tool("list_sessions", "List resumable DeepWrap sessions.", {"type": "object", "properties": {"limit": {"type": "integer", "default": 20}}}),
        )

    @property
    def functions(self) -> dict[str, Any]:
        return {
            "remember": self.remember,
            "recall": self.recall,
            "list_memories": self.list,
            "forget": self.forget,
            "list_sessions": self.list_sessions,
        }
