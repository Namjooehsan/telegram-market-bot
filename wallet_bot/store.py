"""Encrypted SQLite address book. No private keys or seed phrases are stored."""
import os
import sqlite3
from cryptography.fernet import Fernet, InvalidToken


class WalletStore:
    def __init__(self, db_path: str):
        key = os.getenv("WALLET_DATA_KEY", "").strip().encode()
        if not key:
            raise RuntimeError("WALLET_DATA_KEY is required; refusing plaintext wallet storage")
        try:
            self.fernet = Fernet(key)
        except (ValueError, TypeError) as exc:
            raise RuntimeError("WALLET_DATA_KEY must be a valid Fernet key") from exc
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        with self._connect() as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS watched_addresses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    telegram_user_id TEXT NOT NULL,
                    network TEXT NOT NULL,
                    address_ciphertext BLOB NOT NULL,
                    label_ciphertext BLOB NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            db.execute("CREATE INDEX IF NOT EXISTS idx_wallet_owner ON watched_addresses(telegram_user_id)")

    def _connect(self):
        db = sqlite3.connect(self.db_path, timeout=10)
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA foreign_keys=ON")
        return db

    def add(self, user_id: str, network: str, address: str, label: str = "") -> int:
        # Bound storage growth and reduce abuse from repeated /add commands.
        with self._connect() as db:
            count = db.execute("SELECT COUNT(*) FROM watched_addresses WHERE telegram_user_id=?", (str(user_id),)).fetchone()[0]
        if count >= 30:
            raise ValueError("A maximum of 30 addresses is allowed per Telegram account")
        encrypted_address = self.fernet.encrypt(address.encode())
        encrypted_label = self.fernet.encrypt(label.encode())
        with self._connect() as db:
            cur = db.execute(
                "INSERT INTO watched_addresses (telegram_user_id, network, address_ciphertext, label_ciphertext) VALUES (?, ?, ?, ?)",
                (str(user_id), network.upper(), encrypted_address, encrypted_label),
            )
            return int(cur.lastrowid)

    def list_for_user(self, user_id: str):
        with self._connect() as db:
            rows = db.execute(
                "SELECT id, network, address_ciphertext, label_ciphertext, created_at FROM watched_addresses WHERE telegram_user_id=? ORDER BY id DESC",
                (str(user_id),),
            ).fetchall()
        result = []
        for row in rows:
            try:
                address = self.fernet.decrypt(row[2]).decode()
                label = self.fernet.decrypt(row[3]).decode()
            except InvalidToken as exc:
                raise RuntimeError("Wallet data key does not match the key used to encrypt this database") from exc
            result.append({"id": row[0], "network": row[1], "address": address, "label": label, "created_at": row[4]})
        return result

    def remove(self, user_id: str, entry_id: int) -> bool:
        with self._connect() as db:
            cur = db.execute(
                "DELETE FROM watched_addresses WHERE telegram_user_id=? AND id=?",
                (str(user_id), int(entry_id)),
            )
            return cur.rowcount == 1
