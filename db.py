import aiosqlite
from datetime import datetime, timezone


async def init_db(db_path: str) -> None:
    async with aiosqlite.connect(db_path) as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS requests (
                id             INTEGER PRIMARY KEY AUTOINCREMENT,
                message_id     TEXT NOT NULL UNIQUE,
                channel_id     TEXT NOT NULL,
                guild_id       TEXT NOT NULL,
                requester_id   TEXT NOT NULL,
                requester_name TEXT NOT NULL,
                date           TEXT NOT NULL,
                time           TEXT NOT NULL,
                team           TEXT NOT NULL,
                note           TEXT,
                status         TEXT NOT NULL DEFAULT 'OPEN',
                closed_by_id   TEXT,
                closed_by_name TEXT,
                created_at     TEXT NOT NULL
            )
        """)
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS volunteers (
                request_id     INTEGER NOT NULL,
                user_id        TEXT NOT NULL,
                user_name      TEXT NOT NULL,
                volunteered_at TEXT NOT NULL,
                PRIMARY KEY (request_id, user_id),
                FOREIGN KEY (request_id) REFERENCES requests(id)
            )
        """)
        await conn.commit()


async def create_request(
    db_path: str,
    message_id: str,
    channel_id: str,
    guild_id: str,
    requester_id: str,
    requester_name: str,
    date: str,
    time: str,
    team: str,
    note: str | None,
) -> int:
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(db_path) as conn:
        cursor = await conn.execute(
            """
            INSERT INTO requests
                (message_id, channel_id, guild_id, requester_id, requester_name,
                 date, time, team, note, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (message_id, channel_id, guild_id, requester_id, requester_name,
             date, time, team, note, now),
        )
        await conn.commit()
        return cursor.lastrowid


async def get_request_by_message_id(db_path: str, message_id: str) -> dict | None:
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            "SELECT * FROM requests WHERE message_id = ?", (message_id,)
        ) as cursor:
            row = await cursor.fetchone()
            return dict(row) if row else None


async def get_volunteers(db_path: str, request_id: int) -> list[dict]:
    async with aiosqlite.connect(db_path) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute(
            "SELECT * FROM volunteers WHERE request_id = ? ORDER BY volunteered_at",
            (request_id,),
        ) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]


async def toggle_volunteer(
    db_path: str, request_id: int, user_id: str, user_name: str
) -> bool:
    """Returns True if the user is now volunteered, False if they un-volunteered."""
    now = datetime.now(timezone.utc).isoformat()
    async with aiosqlite.connect(db_path) as conn:
        async with conn.execute(
            "SELECT 1 FROM volunteers WHERE request_id = ? AND user_id = ?",
            (request_id, user_id),
        ) as cursor:
            exists = await cursor.fetchone() is not None

        if exists:
            await conn.execute(
                "DELETE FROM volunteers WHERE request_id = ? AND user_id = ?",
                (request_id, user_id),
            )
            await conn.commit()
            return False
        else:
            await conn.execute(
                "INSERT INTO volunteers (request_id, user_id, user_name, volunteered_at) VALUES (?, ?, ?, ?)",
                (request_id, user_id, user_name, now),
            )
            await conn.commit()
            return True


async def close_request(
    db_path: str, message_id: str, closed_by_id: str, closed_by_name: str
) -> bool:
    """Returns False if already closed (idempotent guard), True on success."""
    async with aiosqlite.connect(db_path) as conn:
        async with conn.execute(
            "SELECT status FROM requests WHERE message_id = ?", (message_id,)
        ) as cursor:
            row = await cursor.fetchone()

        if row is None or row[0] == "FILLED":
            return False

        await conn.execute(
            """
            UPDATE requests
            SET status = 'FILLED', closed_by_id = ?, closed_by_name = ?
            WHERE message_id = ?
            """,
            (closed_by_id, closed_by_name, message_id),
        )
        await conn.commit()
        return True
