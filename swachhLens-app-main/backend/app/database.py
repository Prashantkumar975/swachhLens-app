"""Database persistence layer supporting SQLite (local) and PostgreSQL (production).

FastAPI runs sync endpoints in a threadpool, so a single module-level
connection guarded by a lock is safe for both database backends.
"""
from __future__ import annotations

import json
import os
import threading
import time
from typing import Any

from . import config, security
from .constants import ROSTER

_conn: Any = None
_lock = threading.Lock()
_is_postgres = False

def is_postgres() -> bool:
    """Check if we're using PostgreSQL (must call get_conn() first)."""
    get_conn()  # ensure connection is initialized
    return _is_postgres

# Unified schema (compatible with both SQLite and PostgreSQL)
SCHEMA_SQLITE = """
CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY,
    email         TEXT,
    phone         TEXT,
    password_hash TEXT NOT NULL,
    name          TEXT NOT NULL,
    role          TEXT NOT NULL CHECK(role IN ('USER', 'EMPLOYEE')),
    employee_id   TEXT,
    verified      INTEGER NOT NULL DEFAULT 1,
    created_at    INTEGER NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email) WHERE email IS NOT NULL AND email != '';

CREATE TABLE IF NOT EXISTS otp_requests (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     TEXT NOT NULL,
    otp_code    TEXT NOT NULL,
    expires_at  INTEGER NOT NULL,
    verified    INTEGER NOT NULL DEFAULT 0,
    created_at  INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS reports (
    id                  TEXT PRIMARY KEY,
    waste_type          TEXT NOT NULL,
    location            TEXT NOT NULL,
    lat                 REAL,
    lng                 REAL,
    description         TEXT NOT NULL,
    severity            TEXT NOT NULL DEFAULT 'Medium',
    photo               TEXT,
    reporter            TEXT NOT NULL,
    reporter_name       TEXT NOT NULL,
    is_booking          INTEGER NOT NULL DEFAULT 0,
    scheduled_at        INTEGER,
    suggested_group_id  TEXT,
    suggested_member_id TEXT,
    suggestion_reason   TEXT,
    assigned_group_id   TEXT,
    assigned_to         TEXT,
    assigned_by         TEXT,
    proof_photo         TEXT,
    status              TEXT NOT NULL DEFAULT 'PENDING',
    verified_by         TEXT,
    created_at          INTEGER NOT NULL,
    resolved_at         INTEGER,
    history             TEXT NOT NULL DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS idx_reports_reporter        ON reports(reporter);
CREATE INDEX IF NOT EXISTS idx_reports_status          ON reports(status);
CREATE INDEX IF NOT EXISTS idx_reports_assigned_group  ON reports(assigned_group_id);
CREATE INDEX IF NOT EXISTS idx_reports_suggested_group ON reports(suggested_group_id);

CREATE TABLE IF NOT EXISTS bins (
    id               TEXT PRIMARY KEY,
    x                INTEGER NOT NULL,
    y                INTEGER NOT NULL,
    fill             INTEGER NOT NULL DEFAULT 0 CHECK(fill BETWEEN 0 AND 100),
    type             TEXT NOT NULL DEFAULT 'Mixed',
    last_serviced_at INTEGER,
    created_at       INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_bins_type ON bins(type);

CREATE TABLE IF NOT EXISTS fleet (
    id         TEXT PRIMARY KEY,
    driver     TEXT NOT NULL,
    plate      TEXT NOT NULL,
    ward       TEXT NOT NULL DEFAULT 'Ward 4',
    route      TEXT NOT NULL,
    speed_kmh  REAL NOT NULL DEFAULT 24,
    status     TEXT NOT NULL DEFAULT 'ACTIVE'
);

CREATE TABLE IF NOT EXISTS initiatives (
    id           TEXT PRIMARY KEY,
    ngo          TEXT NOT NULL,
    title        TEXT NOT NULL,
    description  TEXT NOT NULL DEFAULT '',
    category     TEXT NOT NULL DEFAULT 'cleanup',
    icon         TEXT NOT NULL DEFAULT '🌱',
    location     TEXT NOT NULL DEFAULT '',
    scheduled_at INTEGER,
    capacity     INTEGER,
    created_at   INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_initiatives_category ON initiatives(category);

CREATE TABLE IF NOT EXISTS initiative_signups (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    initiative_id TEXT NOT NULL REFERENCES initiatives(id),
    user_email    TEXT NOT NULL REFERENCES users(email),
    joined_at     INTEGER NOT NULL,
    UNIQUE(initiative_id, user_email)
);
CREATE INDEX IF NOT EXISTS idx_signups_user ON initiative_signups(user_email);

CREATE TABLE IF NOT EXISTS admin_users (
    id            TEXT PRIMARY KEY,
    user_id       TEXT UNIQUE NOT NULL,
    name          TEXT NOT NULL,
    phone         TEXT,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL CHECK(role IN ('admin', 'employee')),
    created_at    INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_admin_users_user_id ON admin_users(user_id);
CREATE INDEX IF NOT EXISTS idx_admin_users_role ON admin_users(role);

CREATE TABLE IF NOT EXISTS admin_tasks (
    id            TEXT PRIMARY KEY,
    title         TEXT NOT NULL,
    description   TEXT NOT NULL DEFAULT '',
    assigned_to   TEXT REFERENCES admin_users(user_id),
    status        TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'accepted', 'rejected')),
    created_by    TEXT NOT NULL REFERENCES admin_users(user_id),
    created_at    INTEGER NOT NULL,
    updated_at    INTEGER
);
CREATE INDEX IF NOT EXISTS idx_admin_tasks_assigned ON admin_tasks(assigned_to);
CREATE INDEX IF NOT EXISTS idx_admin_tasks_status ON admin_tasks(status);
CREATE INDEX IF NOT EXISTS idx_admin_tasks_created_by ON admin_tasks(created_by);
"""

SCHEMA_POSTGRES = """
CREATE TABLE IF NOT EXISTS users (
    id            TEXT PRIMARY KEY,
    email         TEXT,
    phone         TEXT,
    password_hash TEXT NOT NULL,
    name          TEXT NOT NULL,
    role          TEXT NOT NULL CHECK(role IN ('USER', 'EMPLOYEE')),
    employee_id   TEXT,
    verified      INTEGER NOT NULL DEFAULT 1,
    created_at    BIGINT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_users_email ON users(email) WHERE email IS NOT NULL AND email != '';
DO $$ BEGIN
    ALTER TABLE users ADD CONSTRAINT uq_users_email UNIQUE (email);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

CREATE TABLE IF NOT EXISTS otp_requests (
    id          BIGSERIAL PRIMARY KEY,
    user_id     TEXT NOT NULL,
    otp_code    TEXT NOT NULL,
    expires_at  BIGINT NOT NULL,
    verified    INTEGER NOT NULL DEFAULT 0,
    created_at  BIGINT NOT NULL
);

CREATE TABLE IF NOT EXISTS reports (
    id                  TEXT PRIMARY KEY,
    waste_type          TEXT NOT NULL,
    location            TEXT NOT NULL,
    lat                 REAL,
    lng                 REAL,
    description         TEXT NOT NULL,
    severity            TEXT NOT NULL DEFAULT 'Medium',
    photo               TEXT,
    reporter            TEXT NOT NULL,
    reporter_name       TEXT NOT NULL,
    is_booking          INTEGER NOT NULL DEFAULT 0,
    scheduled_at        BIGINT,
    suggested_group_id  TEXT,
    suggested_member_id TEXT,
    suggestion_reason   TEXT,
    assigned_group_id   TEXT,
    assigned_to         TEXT,
    assigned_by         TEXT,
    proof_photo         TEXT,
    status              TEXT NOT NULL DEFAULT 'PENDING',
    verified_by         TEXT,
    created_at          BIGINT NOT NULL,
    resolved_at         BIGINT,
    history             TEXT NOT NULL DEFAULT '[]'
);

CREATE INDEX IF NOT EXISTS idx_reports_reporter        ON reports(reporter);
CREATE INDEX IF NOT EXISTS idx_reports_status          ON reports(status);
CREATE INDEX IF NOT EXISTS idx_reports_assigned_group  ON reports(assigned_group_id);
CREATE INDEX IF NOT EXISTS idx_reports_suggested_group ON reports(suggested_group_id);

CREATE TABLE IF NOT EXISTS bins (
    id               TEXT PRIMARY KEY,
    x                INTEGER NOT NULL,
    y                INTEGER NOT NULL,
    fill             INTEGER NOT NULL DEFAULT 0 CHECK(fill BETWEEN 0 AND 100),
    type             TEXT NOT NULL DEFAULT 'Mixed',
    last_serviced_at BIGINT,
    created_at       BIGINT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_bins_type ON bins(type);

CREATE TABLE IF NOT EXISTS fleet (
    id         TEXT PRIMARY KEY,
    driver     TEXT NOT NULL,
    plate      TEXT NOT NULL,
    ward       TEXT NOT NULL DEFAULT 'Ward 4',
    route      TEXT NOT NULL,
    speed_kmh  REAL NOT NULL DEFAULT 24,
    status     TEXT NOT NULL DEFAULT 'ACTIVE'
);

CREATE TABLE IF NOT EXISTS initiatives (
    id           TEXT PRIMARY KEY,
    ngo          TEXT NOT NULL,
    title        TEXT NOT NULL,
    description  TEXT NOT NULL DEFAULT '',
    category     TEXT NOT NULL DEFAULT 'cleanup',
    icon         TEXT NOT NULL DEFAULT '🌱',
    location     TEXT NOT NULL DEFAULT '',
    scheduled_at BIGINT,
    capacity     INTEGER,
    created_at   BIGINT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_initiatives_category ON initiatives(category);

CREATE TABLE IF NOT EXISTS initiative_signups (
    id            SERIAL PRIMARY KEY,
    initiative_id TEXT NOT NULL REFERENCES initiatives(id),
    user_email    TEXT NOT NULL REFERENCES users(email),
    joined_at     BIGINT NOT NULL,
    UNIQUE(initiative_id, user_email)
);
CREATE INDEX IF NOT EXISTS idx_signups_user ON initiative_signups(user_email);

CREATE TABLE IF NOT EXISTS admin_users (
    id            TEXT PRIMARY KEY,
    user_id       TEXT UNIQUE NOT NULL,
    name          TEXT NOT NULL,
    phone         TEXT,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL CHECK(role IN ('admin', 'employee')),
    created_at    BIGINT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_admin_users_user_id ON admin_users(user_id);
CREATE INDEX IF NOT EXISTS idx_admin_users_role ON admin_users(role);

CREATE TABLE IF NOT EXISTS admin_tasks (
    id            TEXT PRIMARY KEY,
    title         TEXT NOT NULL,
    description   TEXT NOT NULL DEFAULT '',
    assigned_to   TEXT REFERENCES admin_users(user_id),
    status        TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending', 'accepted', 'rejected')),
    created_by    TEXT NOT NULL REFERENCES admin_users(user_id),
    created_at    BIGINT NOT NULL,
    updated_at    BIGINT
);
CREATE INDEX IF NOT EXISTS idx_admin_tasks_assigned ON admin_tasks(assigned_to);
CREATE INDEX IF NOT EXISTS idx_admin_tasks_status ON admin_tasks(status);
CREATE INDEX IF NOT EXISTS idx_admin_tasks_created_by ON admin_tasks(created_by);
"""


def get_conn():
    """Get database connection (SQLite or PostgreSQL based on DATABASE_URL)."""
    global _conn, _is_postgres

    if _conn is None:
        db_url = config.DATABASE_URL

        if db_url.startswith("postgresql://"):
            # PostgreSQL connection
            import psycopg2
            import psycopg2.extras

            _is_postgres = True
            _conn = psycopg2.connect(db_url)
            _conn.autocommit = False
            print("OK: Connected to PostgreSQL database")
        else:
            # SQLite connection (default for local development)
            import sqlite3

            _is_postgres = False
            db_path = db_url.replace("sqlite:///", "")
            _conn = sqlite3.connect(db_path, check_same_thread=False)
            _conn.row_factory = sqlite3.Row
            _conn.execute("PRAGMA foreign_keys = ON")
            print(f"OK: Connected to SQLite database: {db_path}")

    return _conn


def query(sql: str, params: tuple = ()) -> list[dict]:
    """Execute a SELECT query and return all rows as dicts."""
    with _lock:
        conn = get_conn()
        if _is_postgres:
            import psycopg2.extras
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            # Convert SQLite-style ? placeholders to PostgreSQL %s
            sql = sql.replace("?", "%s")
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            cursor.close()
            return [dict(r) for r in rows]
        else:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]


def query_one(sql: str, params: tuple = ()) -> dict | None:
    """Execute a SELECT query and return the first row as a dict, or None."""
    with _lock:
        conn = get_conn()
        if _is_postgres:
            import psycopg2.extras
            cursor = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
            sql = sql.replace("?", "%s")
            cursor.execute(sql, params)
            row = cursor.fetchone()
            cursor.close()
            return dict(row) if row else None
        else:
            row = conn.execute(sql, params).fetchone()
            return dict(row) if row else None


def execute(sql: str, params: tuple = ()) -> None:
    """Execute an INSERT/UPDATE/DELETE statement."""
    with _lock:
        conn = get_conn()
        if _is_postgres:
            cursor = conn.cursor()
            sql = sql.replace("?", "%s")
            cursor.execute(sql, params)
            conn.commit()
            cursor.close()
        else:
            conn.execute(sql, params)
            conn.commit()


def executemany(sql: str, seq: list[tuple]) -> None:
    """Execute a statement multiple times with different parameters."""
    with _lock:
        conn = get_conn()
        if _is_postgres:
            cursor = conn.cursor()
            sql = sql.replace("?", "%s")
            cursor.executemany(sql, seq)
            conn.commit()
            cursor.close()
        else:
            conn.executemany(sql, seq)
            conn.commit()

_BINS = [
    ("B-1042", 150, 308, 32, "Mixed"),
    ("B-1043", 305, 410, 64, "Mixed"),
    ("B-1044", 475, 228, 88, "High-rise"),
    ("B-1045", 635, 128, 45, "Market"),
    ("B-1046", 700, 292, 72, "Residential"),
    ("B-1047", 410, 205, 20, "Park"),
]
_FLEET = ("TRK-8214", "Rajesh Kumar", "TN-07-KH 8214", "Ward 4",
          "[[60,320],[180,320],[180,420],[320,420],[320,220],[460,220],[460,120],[620,120],[620,300],[760,300]]",
          24.0, "ACTIVE")
_INITIATIVES = [
    ("ini_cleanup_01", "Green Ward Foundation", "Riverfront Clean-up Drive",
     "Join neighbours to clear the Ward 4 riverfront before the monsoon.", "cleanup", "🧹",
     "Adyar Riverfront, Ward 4", 5, 100),
    ("ini_trees_02", "Urban Forest Society", "One Million Trees — Ward 4",
     "Plant native saplings across Ward 4 parks and streets.", "treeplanting", "🌳",
     "North Zone Park", 12, 250),
    ("ini_ewaste_03", "E-Cycle India", "E-Waste Collection Camp",
     "Drop off old electronics and batteries — recycled safely on the spot.", "recycle_drive", "🔌",
     "Community Hall, East Zone", 7, 80),
    ("ini_compost_04", "Eco Residents Association", "Composting Workshop",
     "Hands-on workshop: turn kitchen waste into garden soil.", "workshop", "🌱",
     "West Zone Library", 9, 40),
]
_DAY_MS = 86400000


def _seed_gis() -> None:
    """6 dustbins + 1 truck, mirroring the hardcoded values in js/gis.js."""
    now = int(time.time() * 1000)

    # Use INSERT ... ON CONFLICT for PostgreSQL, INSERT OR IGNORE for SQLite
    if _is_postgres:
        for b in _BINS:
            execute(
                "INSERT INTO bins (id, x, y, fill, type, last_serviced_at, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT (id) DO NOTHING",
                (b[0], b[1], b[2], b[3], b[4], None, now),
            )
        execute(
            "INSERT INTO fleet (id, driver, plate, ward, route, speed_kmh, status)"
            " VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT (id) DO NOTHING",
            _FLEET,
        )
    else:
        executemany(
            "INSERT OR IGNORE INTO bins (id, x, y, fill, type, last_serviced_at, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            [(b[0], b[1], b[2], b[3], b[4], None, now) for b in _BINS],
        )
        execute(
            "INSERT OR IGNORE INTO fleet (id, driver, plate, ward, route, speed_kmh, status)"
            " VALUES (?, ?, ?, ?, ?, ?, ?)",
            _FLEET,
        )


def _seed_initiatives() -> None:
    now = int(time.time() * 1000)

    if _is_postgres:
        for i in _INITIATIVES:
            execute(
                "INSERT INTO initiatives"
                " (id, ngo, title, description, category, icon, location, scheduled_at, capacity, created_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT (id) DO NOTHING",
                (i[0], i[1], i[2], i[3], i[4], i[5], i[6], now + i[7] * _DAY_MS, i[8], now),
            )
    else:
        executemany(
            "INSERT OR IGNORE INTO initiatives"
            " (id, ngo, title, description, category, icon, location, scheduled_at, capacity, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            [(i[0], i[1], i[2], i[3], i[4], i[5], i[6], now + i[7] * _DAY_MS, i[8], now) for i in _INITIATIVES],
        )

def _migrate() -> None:
    """Add columns to pre-existing databases that predate later schema changes."""
    if _is_postgres:
        # PostgreSQL: Check if columns exist
        cols = {
            r["column_name"]
            for r in query(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'reports'"
            )
        }
        if "lat" not in cols:
            execute("ALTER TABLE reports ADD COLUMN lat REAL")
        if "lng" not in cols:
            execute("ALTER TABLE reports ADD COLUMN lng REAL")
        if "assigned_by" not in cols:
            execute("ALTER TABLE reports ADD COLUMN assigned_by TEXT")
        if "proof_photo" not in cols:
            execute("ALTER TABLE reports ADD COLUMN proof_photo TEXT")
    else:
        # SQLite: PRAGMA table_info
        cols = {r["name"] for r in query("PRAGMA table_info(reports)")}
        if "lat" not in cols:
            execute("ALTER TABLE reports ADD COLUMN lat REAL")
        if "lng" not in cols:
            execute("ALTER TABLE reports ADD COLUMN lng REAL")
        if "assigned_by" not in cols:
            execute("ALTER TABLE reports ADD COLUMN assigned_by TEXT")
        if "proof_photo" not in cols:
            execute("ALTER TABLE reports ADD COLUMN proof_photo TEXT")

    # Fix NULL ids in admin_users table (old seed data)
    rows = query("SELECT rowid, user_id FROM admin_users WHERE id IS NULL")
    for r in rows:
        execute("UPDATE admin_users SET id = ? WHERE rowid = ?", (r["user_id"], r["rowid"]))

    # Ensure phone column exists on users table
    if _is_postgres:
        user_cols = {
            r["column_name"]
            for r in query(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'users'"
            )
        }
        if "phone" not in user_cols:
            execute("ALTER TABLE users ADD COLUMN phone TEXT")
    else:
        user_cols = {r["name"] for r in query("PRAGMA table_info(users)")}
        if "phone" not in user_cols:
            execute("ALTER TABLE users ADD COLUMN phone TEXT")

    # Ensure verified column exists on users table (phone-OTP registration)
    if _is_postgres:
        user_cols = {
            r["column_name"]
            for r in query(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'users'"
            )
        }
        if "verified" not in user_cols:
            execute("ALTER TABLE users ADD COLUMN verified INTEGER NOT NULL DEFAULT 1")
    else:
        user_cols = {r["name"] for r in query("PRAGMA table_info(users)")}
        if "verified" not in user_cols:
            execute("ALTER TABLE users ADD COLUMN verified INTEGER NOT NULL DEFAULT 1")

    # Ensure phone column exists on admin_users table (employee phone registration)
    if _is_postgres:
        admin_cols = {
            r["column_name"]
            for r in query(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name = 'admin_users'"
            )
        }
        if "phone" not in admin_cols:
            execute("ALTER TABLE admin_users ADD COLUMN phone TEXT")
    else:
        admin_cols = {r["name"] for r in query("PRAGMA table_info(admin_users)")}
        if "phone" not in admin_cols:
            execute("ALTER TABLE admin_users ADD COLUMN phone TEXT")


# The single agency admin — no pre-seeded employee/demo logins. The admin
# creates crew accounts from the Admin dashboard (Register Employee).
# Credentials come from the environment (config.ADMIN_*). When ADMIN_PASSWORD
# is not set, the seed generates a strong random password and prints it once
# — there is no hard-coded default to leak from the source.
SINGLE_ADMIN = {
    "user_id": config.ADMIN_USER_ID,
    "name": config.ADMIN_NAME,
    "password": config.ADMIN_PASSWORD,
}
# Demo logins that used to ship with the app — removed on upgrade.
LEGACY_DEMO_IDS = ("ADMIN-001", "EMP-001", "EMP-002")


def _seed_admin_accounts() -> None:
    """Ensure exactly one admin account exists; purge legacy demo accounts.

    Old builds seeded demo logins (ADMIN-001/admin123, EMP-001/emp123,
    EMP-002/emp123). Those are deleted and any work still assigned to them
    is released (tasks unassigned / re-owned by the admin, reports back to
    PENDING) so foreign keys stay valid.
    """
    from . import security

    now = int(time.time() * 1000)

    # ---- 1) Remove legacy demo accounts (FK-safe) --------------------
    legacy = [
        uid
        for uid in LEGACY_DEMO_IDS
        if query_one("SELECT 1 FROM admin_users WHERE user_id = ?", (uid,))
    ]
    if legacy:
        marks = ",".join("?" for _ in legacy)
        args = tuple(legacy)
        # Release admin tasks assigned to removed employees / re-own tasks the
        # removed demo admin created.
        execute(f"UPDATE admin_tasks SET assigned_to = NULL WHERE assigned_to IN ({marks})", args)
        execute(f"UPDATE admin_tasks SET created_by = 'ADMIN' WHERE created_by IN ({marks})", args)
        # Reopen citizen reports that were handed to a removed employee.
        execute(f"UPDATE reports SET status = 'PENDING', assigned_to = NULL WHERE assigned_to IN ({marks})", args)
        execute(f"DELETE FROM admin_users WHERE user_id IN ({marks})", args)
        print(f"Removed {len(legacy)} legacy demo account(s): {', '.join(legacy)}")

    # ---- 2) Ensure the single admin exists ---------------------------
    uid = SINGLE_ADMIN["user_id"]
    row = query_one("SELECT id FROM admin_users WHERE user_id = ?", (uid,))
    password = SINGLE_ADMIN["password"]
    if not password:
        # No env override — generate a strong random password (printed once
        # so the first login is possible; set ADMIN_PASSWORD to use your own).
        import secrets as _secrets
        import string as _string

        _alphabet = _string.ascii_letters + _string.digits + "!@#$%^&*"
        password = "".join(_secrets.choice(_alphabet) for _ in range(16))
        print(
            f"ADMIN_PASSWORD not set — generated random password for {uid}: "
            f"{password}"
        )
        print("  Set ADMIN_PASSWORD in the environment to use your own.")
    if not row:
        # Check if a row exists with the same id but different user_id (from a previous config)
        existing_by_id = query_one("SELECT id FROM admin_users WHERE id = ?", ("adm_admin",))
        if existing_by_id:
            execute(
                "UPDATE admin_users SET user_id = ?, name = ?, password_hash = ? WHERE id = ?",
                (uid, SINGLE_ADMIN["name"], security.hash_password(password), "adm_admin"),
            )
            print(f"Updated admin account id to {uid}")
        else:
            execute(
                "INSERT INTO admin_users (id, user_id, name, role, password_hash, created_at)"
                " VALUES (?, ?, ?, 'admin', ?, ?)",
                ("adm_admin", uid, SINGLE_ADMIN["name"],
                 security.hash_password(password), now),
            )
            print(f"Seeded single admin account: {uid}")
    elif SINGLE_ADMIN["password"]:
        # Env override present — always apply it so deployments can rotate
        # the admin password by changing the env var and restarting.
        execute(
            "UPDATE admin_users SET name = ?, password_hash = ? WHERE user_id = ?",
            (SINGLE_ADMIN["name"], security.hash_password(password), uid),
        )
        print(f"Updated admin account {uid} from environment (ADMIN_PASSWORD).")


def init_db() -> None:
    """Initialize database schema and seed demo data."""
    with _lock:
        conn = get_conn()
        schema = SCHEMA_POSTGRES if _is_postgres else SCHEMA_SQLITE

        if _is_postgres:
            cursor = conn.cursor()
            cursor.execute(schema)
            conn.commit()
            cursor.close()
        else:
            conn.executescript(schema)
            conn.commit()

    _migrate()
    _seed_admin_accounts()
    _seed_gis()
    _seed_initiatives()

    print("OK: Database initialized")


def report_from_row(row: dict) -> dict:
    """Convert a DB row (snake_case) to the camelCase shape the frontend expects."""
    return {
        "id": row["id"],
        "wasteType": row["waste_type"],
        "location": row["location"],
        "lat": row.get("lat"),
        "lng": row.get("lng"),
        "desc": row["description"],
        "severity": row["severity"],
        "photo": row["photo"] or "",
        "reporter": row["reporter"],
        "reporterName": row["reporter_name"],
        "isBooking": bool(row["is_booking"]),
        "scheduledAt": row["scheduled_at"],
        "suggestedGroupId": row["suggested_group_id"],
        "suggestedMemberId": row["suggested_member_id"],
        "suggestionReason": row["suggestion_reason"],
        "assignedGroupId": row["assigned_group_id"],
        "assignedTo": row["assigned_to"],
        "status": row["status"],
        "verifiedBy": row["verified_by"],
        "createdAt": row["created_at"],
        "resolvedAt": row["resolved_at"],
        "history": json.loads(row["history"] or "[]"),
    }
