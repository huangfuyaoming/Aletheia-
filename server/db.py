import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path


class Database:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as conn:
            conn.execute('PRAGMA journal_mode=WAL')
            conn.executescript(Path(__file__).with_name('schema.sql').read_text(encoding='utf-8'))
            columns = {row['name'] for row in conn.execute('PRAGMA table_info(messages)')}
            if 'sequence' not in columns:
                conn.execute('ALTER TABLE messages ADD COLUMN sequence INTEGER NOT NULL DEFAULT 0')
                conn.execute('UPDATE messages SET sequence=(SELECT COUNT(*) FROM messages m WHERE m.conversation_id=messages.conversation_id AND m.rowid<=messages.rowid)')
            conn.execute('CREATE UNIQUE INDEX IF NOT EXISTS messages_sequence ON messages(conversation_id, sequence)')
            conn.execute("INSERT OR IGNORE INTO schema_version VALUES (2, strftime('%Y-%m-%dT%H:%M:%fZ','now'))")

    @contextmanager
    def connect(self):
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys=ON')
        try:
            yield conn
            conn.commit()
        except BaseException:
            conn.rollback()
            raise
        finally:
            conn.close()

    def one(self, sql, values=()):
        with self.connect() as conn:
            row = conn.execute(sql, values).fetchone()
            return dict(row) if row else None

    def all(self, sql, values=()):
        with self.connect() as conn:
            return [dict(row) for row in conn.execute(sql, values).fetchall()]

    def execute(self, sql, values=()):
        with self.connect() as conn:
            return conn.execute(sql, values).rowcount


def task_public(row):
    result = json.loads(row['result_json']) if row.get('result_json') else None
    return {key: row.get(key) for key in ('id', 'filename', 'status', 'image_width', 'image_height',
            'error_code', 'error_message', 'created_at', 'started_at', 'finished_at', 'expires_at')} | {'result': result}
