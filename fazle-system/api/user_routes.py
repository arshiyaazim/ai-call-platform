# ============================================================
# Fazle API — User Management Routes
# Full CRUD with pagination for user administration
# ============================================================
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
import logging
import math
from typing import Optional
from datetime import datetime

from auth import require_admin, hash_password
from database import (
    _get_conn, ensure_users_table,
)
from schemas import UserManagementCreate, UserManagementUpdate
from audit import log_action

import psycopg2.extras
import uuid

logger = logging.getLogger("fazle-api")

router = APIRouter(prefix="/fazle/users", tags=["users"])


def _ensure_username_column():
    """Add username column if it doesn't exist (migration-safe)."""
    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns
                        WHERE table_name='fazle_users' AND column_name='username'
                    ) THEN
                        ALTER TABLE fazle_users ADD COLUMN username VARCHAR(100);
                        UPDATE fazle_users SET username = name WHERE username IS NULL;
                    END IF;
                END $$;
            """)
        conn.commit()


@router.on_event("startup")
def user_routes_startup():
    try:
        _ensure_username_column()
    except Exception as e:
        logger.warning(f"Username column migration skipped: {e}")


@router.get("")
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    admin: dict = Depends(require_admin),
):
    """List users with pagination. Admin only."""
    offset = (page - 1) * page_size

    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT COUNT(*) as total FROM fazle_users")
            total = cur.fetchone()["total"]

            cur.execute(
                """SELECT id, email, COALESCE(username, name) as username, name,
                          role, is_active, created_at
                   FROM fazle_users
                   ORDER BY created_at DESC
                   LIMIT %s OFFSET %s""",
                (page_size, offset),
            )
            users = [dict(row) for row in cur.fetchall()]

    # Stringify UUIDs
    for u in users:
        u["id"] = str(u["id"])

    return {
        "users": users,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": math.ceil(total / page_size) if total > 0 else 1,
    }


@router.post("/create")
async def create_user(request: UserManagementCreate, admin: dict = Depends(require_admin)):
    """Create a new user. Admin only."""
    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            # Check existing email
            cur.execute("SELECT id FROM fazle_users WHERE email = %s", (request.email,))
            if cur.fetchone():
                raise HTTPException(status_code=409, detail="Email already registered")

            user_id = uuid.uuid4()
            hashed = hash_password(request.password)
            cur.execute(
                """INSERT INTO fazle_users (id, email, hashed_password, name, username, role)
                   VALUES (%s, %s, %s, %s, %s, %s)
                   RETURNING id, email, name, username, role, is_active, created_at""",
                (user_id, request.email, hashed, request.username, request.username, request.role),
            )
            conn.commit()
            user = dict(cur.fetchone())
            user["id"] = str(user["id"])

    log_action(admin, "create_user", target_type="user", target_id=user["id"],
               detail=f"Created user {request.username} ({request.email})")
    return {"status": "created", "user": user}


@router.put("/update")
async def update_user(
    user_id: str = Query(..., pattern=r"^[a-fA-F0-9\-]+$"),
    request: UserManagementUpdate = None,
    admin: dict = Depends(require_admin),
):
    """Update a user. Admin only."""
    if request is None:
        raise HTTPException(status_code=400, detail="Request body required")

    fields = request.model_dump(exclude_unset=True)
    if not fields:
        raise HTTPException(status_code=400, detail="No fields to update")

    allowed = {"username", "email", "role", "is_active"}
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}

    # Map username to both name and username columns
    if "username" in updates:
        updates["name"] = updates["username"]

    if not updates:
        raise HTTPException(status_code=400, detail="No valid fields to update")

    set_clause = ", ".join(f"{k} = %s" for k in updates)
    values = list(updates.values()) + [user_id]

    with _get_conn() as conn:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(
                f"UPDATE fazle_users SET {set_clause}, updated_at = NOW() WHERE id = %s "
                "RETURNING id, email, COALESCE(username, name) as username, name, role, is_active, created_at",
                values,
            )
            conn.commit()
            row = cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="User not found")
            user = dict(row)
            user["id"] = str(user["id"])

    log_action(admin, "update_user", target_type="user", target_id=user_id,
               detail=str(fields))
    return {"status": "updated", "user": user}


@router.delete("/delete")
async def delete_user(
    user_id: str = Query(..., pattern=r"^[a-fA-F0-9\-]+$"),
    admin: dict = Depends(require_admin),
):
    """Delete a user. Admin only. Cannot delete yourself."""
    if str(admin["id"]) == user_id:
        raise HTTPException(status_code=400, detail="Cannot delete your own account")

    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM fazle_users WHERE id = %s", (user_id,))
            conn.commit()
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="User not found")

    log_action(admin, "delete_user", target_type="user", target_id=user_id)
    return {"status": "deleted"}


@router.post("/reset-password")
async def reset_password(
    user_id: str = Query(..., pattern=r"^[a-fA-F0-9\-]+$"),
    admin: dict = Depends(require_admin),
):
    """Reset a user's password to a random value. Admin only."""
    import secrets
    new_password = secrets.token_urlsafe(16)
    hashed = hash_password(new_password)

    with _get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE fazle_users SET hashed_password = %s, updated_at = NOW() WHERE id = %s",
                (hashed, user_id),
            )
            conn.commit()
            if cur.rowcount == 0:
                raise HTTPException(status_code=404, detail="User not found")

    log_action(admin, "reset_password", target_type="user", target_id=user_id)
    return {"status": "password_reset", "temporary_password": new_password}
