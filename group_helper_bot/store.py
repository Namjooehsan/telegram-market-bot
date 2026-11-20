"""Small persistent SQLite store for group rules, warnings and support reports."""
import os
import sqlite3


class GroupStore:
    def __init__(self, db_path: str):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        with self._connect() as db:
            db.execute("""CREATE TABLE IF NOT EXISTS group_rules (
                chat_id TEXT PRIMARY KEY, rules TEXT NOT NULL, updated_by TEXT NOT NULL,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )""")
            db.execute("""CREATE TABLE IF NOT EXISTS warnings (
                chat_id TEXT NOT NULL, user_id TEXT NOT NULL, count INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY(chat_id, user_id)
            )""")
            db.execute("""CREATE TABLE IF NOT EXISTS support_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT NOT NULL,
                username TEXT NOT NULL DEFAULT '', report TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )""")

    def _connect(self):
        return sqlite3.connect(self.db_path, timeout=10)

    def set_rules(self, chat_id, rules, admin_id):
        with self._connect() as db:
            db.execute(
                """INSERT INTO group_rules(chat_id, rules, updated_by)
                VALUES(?, ?, ?) ON CONFLICT(chat_id) DO UPDATE SET
                rules=excluded.rules, updated_by=excluded.updated_by,
                updated_at=CURRENT_TIMESTAMP""",
                (str(chat_id), rules[:3500], str(admin_id)),
            )

    def get_rules(self, chat_id):
        with self._connect() as db:
            row = db.execute("SELECT rules FROM group_rules WHERE chat_id=?", (str(chat_id),)).fetchone()
        return row[0] if row else None

    def add_warning(self, chat_id, user_id):
        with self._connect() as db:
            db.execute(
                """INSERT INTO warnings(chat_id, user_id, count) VALUES(?, ?, 1)
                ON CONFLICT(chat_id, user_id) DO UPDATE SET
                count=count+1, updated_at=CURRENT_TIMESTAMP""",
                (str(chat_id), str(user_id)),
            )
            row = db.execute(
                "SELECT count FROM warnings WHERE chat_id=? AND user_id=?",
                (str(chat_id), str(user_id)),
            ).fetchone()
        return row[0]

    def add_report(self, user_id, username, report):
        with self._connect() as db:
            cur = db.execute(
                "INSERT INTO support_reports(user_id, username, report) VALUES(?, ?, ?)",
                (str(user_id), (username or "")[:80], report[:2000]),
            )
            return int(cur.lastrowid)
