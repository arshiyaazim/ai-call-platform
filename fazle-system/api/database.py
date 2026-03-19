# ============================================================
# Fazle API — PostgreSQL Database Layer
# User management with async connection pool
# ============================================================
import logging
import uuid
from datetime import datetime
from typing import Optional

import psycopg2
import psycopg2.extras
import psycopg2.pool
from contextlib import contextmanager
from pydantic_settings import BaseSettings

logger = logging.getLogger("fazle-api")

psycopg2.extras.register_uuid()


class DBSettings(BaseSettings):
    database_url: str = "postgresql://postgres:postgres@postgres:5432/postgres"

    class Config:
        env_prefix = "FAZLE_"


db_settings = DBSettings()

_DSN = db_settings.database_url

# Connection pool: min 2, max 10 connections
_pool = psycopg2.pool.ThreadedConnectionPool(2, 10, _DSN)


@contextmanager
def _get_conn():
    conn = _pool.getconn()
    try:
        yield conn
    finally:
        _pool.putconn(conn)


def _put_conn(conn):
    _pool.putconn(conn)


@contextmanager
def _rls_conn(user_id: Optional[str] = None, is_admin: bool = False):
    """Get a connection with RLS session variables set."""
    conn = _get_conn()
    try:
        with conn.cursor() as cur:
            if user_id:
                cur.execute("SET LOCAL app.current_user_id = %s", (str(user_id),))
            if is_admin:
                cur.execute("SET LOCAL app.is_admin = 'true'")
        yield conn
    finally:
        _put_conn(conn)


def ensure_users_table():
    """Create users and conversations tables if they don't exist (idempotent)."""
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS fazle_users (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    email VARCHAR(255) UNIQUE NOT NULL,
                    hashed_password VARCHAR(255) NOT NULL,
                    name VARCHAR(100) NOT NULL,
                    relationship_to_azim VARCHAR(50) NOT NULL DEFAULT 'self',
                    role VARCHAR(20) NOT NULL DEFAULT 'member',
                    is_active BOOLEAN DEFAULT true,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_fazle_users_email ON fazle_users (email);

                CREATE TABLE IF NOT EXISTS fazle_conversations (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    user_id UUID NOT NULL REFERENCES fazle_users(id) ON DELETE CASCADE,
                    conversation_id VARCHAR(100) NOT NULL,
                    title VARCHAR(200) DEFAULT '',
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    UNIQUE(conversation_id)
                );
                CREATE INDEX IF NOT EXISTS idx_fazle_conv_user ON fazle_conversations (user_id);

                CREATE TABLE IF NOT EXISTS fazle_messages (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    conversation_id UUID NOT NULL REFERENCES fazle_conversations(id) ON DELETE CASCADE,
                    role VARCHAR(20) NOT NULL,
                    content TEXT NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                );
                CREATE INDEX IF NOT EXISTS idx_fazle_msg_conv ON fazle_messages (conversation_id);
            """)
        conn.commit()
    logger.info("fazle_users, fazle_conversations, fazle_messages tables ensured")


def create_user(
    email: str,
    hashed_password: str,
    name: str,
    relationship_to_azim: str = "self",
    role: str = "member",
) -> dict:
    """Insert a new user, return the user dict (without password)."""
    user_id = uuid.uuid4()
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                INSERT INTO fazle_users (id, email, hashed_password, name, relationship_to_azim, role)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING id, email, name, relationship_to_azim, role, is_active, created_at
                """,
                (user_id, email, hashed_password, name, relationship_to_azim, role),
            )
            conn.commit()
            return dict(cur.fetchone())


def get_user_by_email(email: str) -> Optional[dict]:
    """Fetch user by email (includes hashed_password for verification)."""
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT id, email, hashed_password, name, relationship_to_azim, role, is_active, created_at FROM fazle_users WHERE email = %s",
                (email,),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def get_user_by_id(user_id: str) -> Optional[dict]:
    """Fetch user by ID (without password)."""
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT id, email, name, relationship_to_azim, role, is_active, created_at FROM fazle_users WHERE id = %s",
                (user_id,),
            )
            row = cur.fetchone()
            return dict(row) if row else None


def list_family_members() -> list[dict]:
    """List all family members (without passwords)."""
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                "SELECT id, email, name, relationship_to_azim, role, is_active, created_at FROM fazle_users ORDER BY created_at"
            )
            return [dict(row) for row in cur.fetchall()]


def update_user(user_id: str, **fields) -> Optional[dict]:
    """Update user fields. Returns updated user or None."""
    allowed = {"name", "relationship_to_azim", "role", "is_active"}
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not updates:
        return get_user_by_id(user_id)

    set_clause = ", ".join(f"{k} = %s" for k in updates)
    values = list(updates.values()) + [user_id]

    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"UPDATE fazle_users SET {set_clause}, updated_at = NOW() WHERE id = %s "
                "RETURNING id, email, name, relationship_to_azim, role, is_active, created_at",
                values,
            )
            conn.commit()
            row = cur.fetchone()
            return dict(row) if row else None


def delete_user(user_id: str) -> bool:
    """Delete a user. Returns True if deleted."""
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM fazle_users WHERE id = %s", (user_id,))
            conn.commit()
            return cur.rowcount > 0


def count_users() -> int:
    """Count total users."""
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM fazle_users")
            return cur.fetchone()[0]


# ── Conversation persistence ────────────────────────────────

def save_message(user_id: str, conversation_id: str, role: str, content: str, title: str = ""):
    """Save a chat message. Creates or updates the conversation record."""
    with _rls_conn(user_id) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Upsert conversation
            cur.execute(
                """
                INSERT INTO fazle_conversations (user_id, conversation_id, title)
                VALUES (%s, %s, %s)
                ON CONFLICT (conversation_id) DO UPDATE SET updated_at = NOW()
                RETURNING id
                """,
                (user_id, conversation_id, title[:200] if title else ""),
            )
            conv_row = cur.fetchone()
            conv_uuid = conv_row["id"]
            # Insert message
            cur.execute(
                """
                INSERT INTO fazle_messages (conversation_id, role, content)
                VALUES (%s, %s, %s)
                """,
                (conv_uuid, role, content),
            )
        conn.commit()


def get_user_conversations(user_id: str, limit: int = 30) -> list[dict]:
    """List conversations for a user, newest first."""
    with _rls_conn(user_id) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT c.conversation_id, c.title, c.created_at, c.updated_at,
                       (SELECT content FROM fazle_messages WHERE conversation_id = c.id ORDER BY created_at DESC LIMIT 1) AS last_message
                FROM fazle_conversations c
                WHERE c.user_id = %s
                ORDER BY c.updated_at DESC
                LIMIT %s
                """,
                (user_id, limit),
            )
            return [dict(r) for r in cur.fetchall()]


def get_conversation_messages(conversation_id: str, user_id: str = None) -> list[dict]:
    """Get messages for a conversation. If user_id given, verify ownership."""
    with _rls_conn(user_id) as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            if user_id:
                cur.execute(
                    """
                    SELECT m.role, m.content, m.created_at
                    FROM fazle_messages m
                    JOIN fazle_conversations c ON c.id = m.conversation_id
                    WHERE c.conversation_id = %s AND c.user_id = %s
                    ORDER BY m.created_at
                    """,
                    (conversation_id, user_id),
                )
            else:
                # Admin: no user filter
                cur.execute(
                    """
                    SELECT m.role, m.content, m.created_at
                    FROM fazle_messages m
                    JOIN fazle_conversations c ON c.id = m.conversation_id
                    WHERE c.conversation_id = %s
                    ORDER BY m.created_at
                    """,
                    (conversation_id,),
                )
            return [dict(r) for r in cur.fetchall()]


def get_all_conversations(limit: int = 50) -> list[dict]:
    """Admin: list all conversations across all users."""
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                """
                SELECT c.conversation_id, c.title, c.created_at, c.updated_at,
                       u.name AS user_name, u.relationship_to_azim,
                       (SELECT content FROM fazle_messages WHERE conversation_id = c.id ORDER BY created_at DESC LIMIT 1) AS last_message
                FROM fazle_conversations c
                JOIN fazle_users u ON u.id = c.user_id
                ORDER BY c.updated_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            return [dict(r) for r in cur.fetchall()]
