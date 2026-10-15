import sqlite3
from pathlib import Path

from flask import current_app, g

DEFAULT_DB_PATH = "cs188_a3.db"

class Database:
    def __init__(self, path: str | Path = DEFAULT_DB_PATH) -> None:
        self.conn = sqlite3.connect(path)
        self.create_users_table()

    def create_users_table(self):
        with self.conn:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username TEXT NOT NULL UNIQUE,
                    password TEXT NOT NULL
                )
                """
            )

    def add_user(self, username, hashed_pwd):
        try:
            with self.conn:
                self.conn.execute(
                    "INSERT INTO users (username, password) VALUES (?, ?)",
                    (username, hashed_pwd),
                )
            return True
        except sqlite3.IntegrityError:
            return False

    def get_password(self, username) -> str | None:
        row = self.conn.execute(
            "SELECT password FROM users WHERE username = ?",
            (username,),).fetchone()
        return row[0] if row else None

def get_db() -> Database:
    """Return the per-request Database, creating it on first use."""
    if "db" not in g:
        g.db = Database(current_app.config["DB_PATH"])
    return g.db