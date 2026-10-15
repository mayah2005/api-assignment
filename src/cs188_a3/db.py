import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import current_app, g

DEFAULT_DB_PATH = "cs188_a3.db"

class Database:
    def __init__(self, path: str | Path = DEFAULT_DB_PATH) -> None:
        """Open the database at `path` and ensure tables exist."""
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row  # rows support access by column name
        self.create_users_table()
        self.create_roster_table()

    def create_users_table(self) -> None:
        """Create the users table if it does not exist."""
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

    def add_user(self, username: str, hashed_pwd: str) -> int | None:
        try:
            with self.conn:
                cursor = self.conn.execute(
                    "INSERT INTO users (username, password) VALUES (?, ?)",
                    (username, hashed_pwd),
                )
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            return None

    def get_user_credentials(self, username: str) -> tuple[int, str] | None:
        row = self.conn.execute(
            "SELECT id, password FROM users WHERE username = ?",
            (username,),
        ).fetchone()
        return (row[0], row[1]) if row else None
    
    def create_roster_table(self) -> None:
        with self.conn:
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS roster (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    owner_id INTEGER NOT NULL REFERENCES users(id),
                    character TEXT NOT NULL,
                    nickname TEXT,
                    level INTEGER NOT NULL,
                    constellation INTEGER NOT NULL,
                    role TEXT NOT NULL,
                    notes TEXT,
                    vision TEXT,
                    weapon_type TEXT,
                    rarity INTEGER,
                    created_at TEXT NOT NULL
                )
                """
            )

    def add_entry(self, owner_id: int, fields: dict[str, Any]) -> int:
        created_at = datetime.now(timezone.utc).isoformat()  # set by the server
        with self.conn:
            cursor = self.conn.execute(
                """
                INSERT INTO roster (owner_id, character, nickname, level,
                    constellation, role, notes, vision, weapon_type, rarity,
                    created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    owner_id, fields["character"], fields["nickname"],
                    fields["level"], fields["constellation"], fields["role"],
                    fields["notes"], fields["vision"], fields["weapon_type"],
                    fields["rarity"], created_at,
                ),
            )
        return cursor.lastrowid

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT * FROM roster WHERE id = ?", (entry_id,)
        ).fetchone()
        return dict(row) if row else None

    def list_entries(
        self,
        role: str | None,
        vision: str | None,
        min_level: int | None,
        limit: int,
        offset: int,
    ) -> list[dict[str, Any]]:
        rows = self.conn.execute(
            """
            SELECT * FROM roster
            WHERE (? IS NULL OR role = ?)
              AND (? IS NULL OR LOWER(vision) = ?)
              AND (? IS NULL OR level >= ?)
            ORDER BY id LIMIT ? OFFSET ?
            """,
            (role, role, vision, vision, min_level, min_level, limit, offset),
        ).fetchall()
        return [dict(row) for row in rows]

    def update_entry(self, entry_id: int, fields: dict[str, Any]) -> None:
        with self.conn:
            self.conn.execute(
                """
                UPDATE roster SET character = ?, nickname = ?, level = ?,
                    constellation = ?, role = ?, notes = ?, vision = ?,
                    weapon_type = ?, rarity = ?
                WHERE id = ?
                """,
                (
                    fields["character"], fields["nickname"], fields["level"],
                    fields["constellation"], fields["role"], fields["notes"],
                    fields["vision"], fields["weapon_type"], fields["rarity"],
                    entry_id,
                ),
            )

    def delete_entry(self, entry_id: int) -> None:
        with self.conn:
            self.conn.execute("DELETE FROM roster WHERE id = ?", (entry_id,))

def get_db() -> Database:
    if "db" not in g:
        g.db = Database(current_app.config["DB_PATH"])
    return g.db