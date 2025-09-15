import os
import sqlite3
from flask import g
from werkzeug.security import generate_password_hash
from datetime import datetime, timedelta
import sys


# ------------------------------
# Database path handling
# ------------------------------


def get_db_path():
    try:
        from android.storage import app_storage_path
        db_dir = app_storage_path()
    except ImportError:
        if getattr(sys, 'frozen', False):
            # Running as exe -> use "_internal" next to exe
            exe_dir = os.path.dirname(sys.executable)
            db_dir = os.path.join(exe_dir, "_internal")
        else:
            # Running from source
            db_dir = os.path.dirname(os.path.abspath(__file__))

    if not os.path.exists(db_dir):
        os.makedirs(db_dir)
    return os.path.join(db_dir, "labor.db")

DB_PATH = get_db_path()


# ------------------------------
# Request-scoped DB (Flask only)
# ------------------------------
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON;")
    return g.db


def close_db(exception=None):
    db = g.pop("db", None)
    if db:
        db.close()


# ------------------------------
# User site filter helper
# ------------------------------
def get_user_site_filter(user_id, role, conn=None):
    if role == "admin":
        return None
    close_conn = False
    if conn is None:
        conn = get_conn()
        close_conn = True
    cur = conn.cursor()
    cur.execute("SELECT site_id FROM site_assignments WHERE user_id=?", (user_id,))
    site_ids = [row["site_id"] for row in cur.fetchall()]
    print("User ID:", user_id, "Role:", role, "Site IDs:", site_ids)
    if close_conn:
        conn.close()
    return site_ids


# ------------------------------
# Standalone DB connection
# ------------------------------
def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


# ------------------------------
# Migration helper
# ------------------------------
def migrate_local_db(conn):
    cursor = conn.cursor()
    # Ensure clients table has is_demo column
    cursor.execute("PRAGMA table_info(clients)")
    cols = [c[1] for c in cursor.fetchall()]
    if "is_demo" not in cols:
        cursor.execute("ALTER TABLE clients ADD COLUMN is_demo INTEGER DEFAULT 0")

    # Ensure users table has client_id column
    cursor.execute("PRAGMA table_info(users)")
    cols = [c[1] for c in cursor.fetchall()]
    if "client_id" not in cols:
        cursor.execute("ALTER TABLE users ADD COLUMN client_id TEXT")

    conn.commit()

# ------------------------------
# Insert into Local helper
# ------------------------------
def insert_into_local(conn, table, row):
    cursor = conn.cursor()
    keys = ", ".join(row.keys())
    placeholders = ", ".join(["?"] * len(row))
    values = list(row.values())
    cursor.execute(f"INSERT OR IGNORE INTO {table} ({keys}) VALUES ({placeholders})", values)
    conn.commit()
# ------------------------------
# Initialize DB
# ------------------------------
def init_db():
    conn = get_conn()
    cur = conn.cursor()
    now = datetime.now()
    demo_days = 7
    max_users = 5
    license_key = "DEMO-12345"

    # ------------------------------
    # 1. Create all tables
    # ------------------------------
    tables = [
        """CREATE TABLE IF NOT EXISTS clients (
            client_id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_code TEXT UNIQUE,
            name TEXT NOT NULL,
            email TEXT UNIQUE,
            phone TEXT,
            address TEXT,
            is_active INTEGER DEFAULT 1,
            subscription_start TEXT,
            subscription_end TEXT,
            demo_days INTEGER DEFAULT 15,
            is_demo INTEGER DEFAULT 0,
            license_key TEXT UNIQUE,
            license_expiry TEXT,
            max_users INTEGER DEFAULT 10,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            uuid TEXT UNIQUE DEFAULT (lower(hex(randomblob(16)))),
            sync_status TEXT DEFAULT 'pending'
        )""",
        """CREATE TABLE IF NOT EXISTS plans (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            sites INTEGER,
            users_per_site INTEGER,
            yearly_price INTEGER,
            monthly_price INTEGER,
            notes TEXT,
            active_offer INTEGER DEFAULT 0,
            offer_price INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            uuid TEXT UNIQUE DEFAULT (lower(hex(randomblob(16)))),
            sync_status TEXT DEFAULT 'pending'
        )""",
        """CREATE TABLE IF NOT EXISTS subscription_payments (
            id TEXT PRIMARY KEY,
            client_id TEXT NOT NULL,
            plan_id TEXT NOT NULL,
            amount REAL NOT NULL,
            plan_type TEXT NOT NULL,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            uuid TEXT UNIQUE DEFAULT (lower(hex(randomblob(16)))),
            sync_status TEXT DEFAULT 'pending'
        )""",
        """CREATE TABLE IF NOT EXISTS licenses (
            id TEXT PRIMARY KEY,
            client_id TEXT NOT NULL,
            plan_id TEXT NOT NULL,
            start_date TEXT NOT NULL,
            end_date TEXT NOT NULL,
            status TEXT DEFAULT 'active',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            uuid TEXT UNIQUE DEFAULT (lower(hex(randomblob(16)))),
            sync_status TEXT DEFAULT 'pending',
            FOREIGN KEY (plan_id) REFERENCES plans (id)
        )""",
        """CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            username TEXT UNIQUE NOT NULL,
            email TEXT UNIQUE,
            role TEXT CHECK(role IN ('admin','engineer','viewer','helper')) NOT NULL DEFAULT 'viewer',
            password TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            is_demo INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            uuid TEXT UNIQUE DEFAULT (lower(hex(randomblob(16)))),
            sync_status TEXT DEFAULT 'pending',
            FOREIGN KEY(client_id) REFERENCES clients(client_id) ON DELETE CASCADE,
            UNIQUE (client_id, username),   -- 👈 tenant-scoped usernames
            UNIQUE (client_id, email)       -- 👈 optional: tenant-scoped emails
        )""",
        """CREATE TABLE IF NOT EXISTS sites (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            location TEXT,
            start_date TEXT,
            end_date TEXT,
            budget REAL DEFAULT 0,   -- new column
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            uuid TEXT UNIQUE DEFAULT (lower(hex(randomblob(16)))),
            sync_status TEXT DEFAULT 'pending',
            FOREIGN KEY(client_id) REFERENCES clients(client_id) ON DELETE CASCADE
        )""",
        """CREATE TABLE IF NOT EXISTS labors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            site_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            address TEXT,
            phone TEXT,
            age INTEGER,
            role TEXT,
            upi TEXT,
            bank TEXT,
            aadhaar TEXT,
            emergency TEXT,
            wages REAL,
            is_active INTEGER DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            uuid TEXT UNIQUE DEFAULT (lower(hex(randomblob(16)))),
            sync_status TEXT DEFAULT 'pending',
            FOREIGN KEY(site_id) REFERENCES sites(id) ON DELETE CASCADE,
            FOREIGN KEY(client_id) REFERENCES clients(client_id) ON DELETE CASCADE
        )""",
        """CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            site_id INTEGER NOT NULL,
            labor_id INTEGER NOT NULL,
            week_start TEXT NOT NULL,
            day TEXT NOT NULL,
            status TEXT,
            extra_hours REAL DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            uuid TEXT UNIQUE DEFAULT (lower(hex(randomblob(16)))),
            sync_status TEXT DEFAULT 'pending',
            UNIQUE(client_id, labor_id, site_id, week_start, day),
            FOREIGN KEY(labor_id) REFERENCES labors(id),
            FOREIGN KEY(site_id) REFERENCES sites(id) ON DELETE CASCADE,
            FOREIGN KEY(client_id) REFERENCES clients(client_id) ON DELETE CASCADE
        )""",
        """CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            labor_id INTEGER,
            site_id INTEGER,
            week_start TEXT,
            total_hours REAL,
            advance REAL DEFAULT 0,
            advance_deduction REAL DEFAULT 0,
            remaining_advance REAL DEFAULT 0,
            payment REAL DEFAULT 0,
            payment_after_deduction REAL DEFAULT 0,
            remarks TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            uuid TEXT UNIQUE DEFAULT (lower(hex(randomblob(16)))),
            sync_status TEXT DEFAULT 'pending',
            UNIQUE(client_id, labor_id, site_id, week_start),
            FOREIGN KEY(client_id) REFERENCES clients(client_id) ON DELETE CASCADE
        )""",
        """CREATE TABLE IF NOT EXISTS site_materials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            site_id INTEGER,
            date TEXT NOT NULL,
            material_name TEXT NOT NULL,
            remarks TEXT,
            quantity REAL,
            unit_price REAL,
            total REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            uuid TEXT UNIQUE DEFAULT (lower(hex(randomblob(16)))),
            sync_status TEXT DEFAULT 'pending',
            FOREIGN KEY(site_id) REFERENCES sites(id) ON DELETE CASCADE,
            FOREIGN KEY(client_id) REFERENCES clients(client_id) ON DELETE CASCADE
        )""",
        """CREATE TABLE IF NOT EXISTS site_expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            site_id INTEGER,
            date TEXT NOT NULL DEFAULT (DATE('now')),
            description TEXT,
            remarks TEXT,
            amount REAL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            uuid TEXT UNIQUE DEFAULT (lower(hex(randomblob(16)))),
            sync_status TEXT DEFAULT 'pending',
            FOREIGN KEY(site_id) REFERENCES sites(id) ON DELETE CASCADE,
            FOREIGN KEY(client_id) REFERENCES clients(client_id) ON DELETE CASCADE
        )""",
        """CREATE TABLE IF NOT EXISTS site_assignments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            client_id INTEGER NOT NULL,
            site_id INTEGER NOT NULL,
            assigned_at TEXT DEFAULT CURRENT_TIMESTAMP,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            uuid TEXT UNIQUE DEFAULT (lower(hex(randomblob(16)))),
            sync_status TEXT DEFAULT 'pending',
            UNIQUE(client_id, user_id, site_id),
            FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY(site_id) REFERENCES sites(id) ON DELETE CASCADE,
            FOREIGN KEY(client_id) REFERENCES clients(client_id) ON DELETE CASCADE
        )""",
        """CREATE TABLE IF NOT EXISTS business_info (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL UNIQUE,
            name TEXT NOT NULL,
            address TEXT,
            phone TEXT,
            email TEXT,
            gst_number TEXT,
            logo TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
            uuid TEXT UNIQUE DEFAULT (lower(hex(randomblob(16)))),
            sync_status TEXT DEFAULT 'pending',
            FOREIGN KEY(client_id) REFERENCES clients(client_id) ON DELETE CASCADE
        )"""
    ]
    for t in tables:
        cur.execute(t)

    # ------------------------------
    # 2. Indexes
    # ------------------------------
    cur.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_attendance_unique
        ON attendance (client_id, site_id, labor_id, week_start, day)
    """)

    # ------------------------------
    # 3. Drop old triggers
    # ------------------------------
    cur.executescript("""
        DROP TRIGGER IF EXISTS trg_attendance_after_insert;
        DROP TRIGGER IF EXISTS trg_attendance_after_update;
        DROP TRIGGER IF EXISTS trg_attendance_after_delete;
        DROP TRIGGER IF EXISTS trg_update_remaining_advance;
        DROP TRIGGER IF EXISTS trg_update_remaining_advance_upd;
    """)

    # ------------------------------
    # 4. Create triggers
    # ------------------------------
    triggers = """
    -- AFTER INSERT
    CREATE TRIGGER trg_attendance_after_insert
    AFTER INSERT ON attendance
    BEGIN
        INSERT OR IGNORE INTO payments (client_id, labor_id, site_id, week_start, remarks)
        VALUES (NEW.client_id, NEW.labor_id, NEW.site_id, NEW.week_start, 'Auto-created');

        UPDATE payments
        SET 
            total_hours = COALESCE((SELECT SUM(
                CASE WHEN status='FD' THEN 8+COALESCE(extra_hours,0)
                     WHEN status='HD' THEN 4+COALESCE(extra_hours,0)
                     ELSE COALESCE(extra_hours,0) END
            ) FROM attendance WHERE labor_id=NEW.labor_id AND site_id=NEW.site_id AND week_start=NEW.week_start AND client_id=NEW.client_id),0),
            payment = COALESCE((SELECT SUM(
                CASE WHEN status='FD' THEN (8+COALESCE(extra_hours,0))*l.wages/8
                     WHEN status='HD' THEN (4+COALESCE(extra_hours,0))*l.wages/8
                     ELSE (COALESCE(extra_hours,0))*l.wages/8 END
            ) FROM attendance a JOIN labors l ON a.labor_id=l.id
            WHERE a.labor_id=NEW.labor_id AND a.site_id=NEW.site_id AND a.week_start=NEW.week_start AND a.client_id=NEW.client_id),0),
            payment_after_deduction = COALESCE((SELECT SUM(
                CASE WHEN status='FD' THEN (8+COALESCE(extra_hours,0))*l.wages/8
                     WHEN status='HD' THEN (4+COALESCE(extra_hours,0))*l.wages/8
                     ELSE (COALESCE(extra_hours,0))*l.wages/8 END
            ) FROM attendance a JOIN labors l ON a.labor_id=l.id
            WHERE a.labor_id=NEW.labor_id AND a.site_id=NEW.site_id AND a.week_start=NEW.week_start AND a.client_id=NEW.client_id),0)-COALESCE(advance_deduction,0)
        WHERE labor_id=NEW.labor_id AND site_id=NEW.site_id AND week_start=NEW.week_start AND client_id=NEW.client_id;
    END;

    -- AFTER UPDATE
    CREATE TRIGGER trg_attendance_after_update
    AFTER UPDATE ON attendance
    BEGIN
        UPDATE payments
        SET 
            total_hours = COALESCE((SELECT SUM(
                CASE WHEN status='FD' THEN 8+COALESCE(extra_hours,0)
                     WHEN status='HD' THEN 4+COALESCE(extra_hours,0)
                     ELSE COALESCE(extra_hours,0) END
            ) FROM attendance WHERE labor_id=NEW.labor_id AND site_id=NEW.site_id AND week_start=NEW.week_start AND client_id=NEW.client_id),0),
            payment = COALESCE((SELECT SUM(
                CASE WHEN status='FD' THEN (8+COALESCE(extra_hours,0))*l.wages/8
                     WHEN status='HD' THEN (4+COALESCE(extra_hours,0))*l.wages/8
                     ELSE (COALESCE(extra_hours,0))*l.wages/8 END
            ) FROM attendance a JOIN labors l ON a.labor_id=l.id
            WHERE a.labor_id=NEW.labor_id AND a.site_id=NEW.site_id AND a.week_start=NEW.week_start AND a.client_id=NEW.client_id),0),
            payment_after_deduction = COALESCE((SELECT SUM(
                CASE WHEN status='FD' THEN (8+COALESCE(extra_hours,0))*l.wages/8
                     WHEN status='HD' THEN (4+COALESCE(extra_hours,0))*l.wages/8
                     ELSE (COALESCE(extra_hours,0))*l.wages/8 END
            ) FROM attendance a JOIN labors l ON a.labor_id=l.id
            WHERE a.labor_id=NEW.labor_id AND a.site_id=NEW.site_id AND a.week_start=NEW.week_start AND a.client_id=NEW.client_id),0)-COALESCE(advance_deduction,0)
        WHERE labor_id=NEW.labor_id AND site_id=NEW.site_id AND week_start=NEW.week_start AND client_id=NEW.client_id;
    END;

    -- AFTER DELETE
    CREATE TRIGGER trg_attendance_after_delete
    AFTER DELETE ON attendance
    BEGIN
        UPDATE payments
        SET 
            total_hours = COALESCE((SELECT SUM(
                CASE WHEN status='FD' THEN 8+COALESCE(extra_hours,0)
                     WHEN status='HD' THEN 4+COALESCE(extra_hours,0)
                     ELSE COALESCE(extra_hours,0) END
            ) FROM attendance WHERE labor_id=OLD.labor_id AND site_id=OLD.site_id AND week_start=OLD.week_start AND client_id=OLD.client_id),0),
            payment = COALESCE((SELECT SUM(
                CASE WHEN status='FD' THEN (8+COALESCE(extra_hours,0))*l.wages/8
                     WHEN status='HD' THEN (4+COALESCE(extra_hours,0))*l.wages/8
                     ELSE (COALESCE(extra_hours,0))*l.wages/8 END
            ) FROM attendance a JOIN labors l ON a.labor_id=l.id
            WHERE a.labor_id=OLD.labor_id AND a.site_id=OLD.site_id AND a.week_start=OLD.week_start AND a.client_id=OLD.client_id),0),
            payment_after_deduction = COALESCE((SELECT SUM(
                CASE WHEN status='FD' THEN (8+COALESCE(extra_hours,0))*l.wages/8
                     WHEN status='HD' THEN (4+COALESCE(extra_hours,0))*l.wages/8
                     ELSE (COALESCE(extra_hours,0))*l.wages/8 END
            ) FROM attendance a JOIN labors l ON a.labor_id=l.id
            WHERE a.labor_id=OLD.labor_id AND a.site_id=OLD.site_id AND a.week_start=OLD.week_start AND a.client_id=OLD.client_id),0)-COALESCE(advance_deduction,0)
        WHERE labor_id=OLD.labor_id AND site_id=OLD.site_id AND week_start=OLD.week_start AND client_id=OLD.client_id;
    END;

    -- Payments advance triggers
    CREATE TRIGGER trg_update_remaining_advance
    AFTER INSERT ON payments
    BEGIN
        UPDATE payments
        SET remaining_advance = NEW.advance - NEW.advance_deduction,
            payment_after_deduction = NEW.payment - NEW.advance_deduction
        WHERE id = NEW.id;
    END;

    CREATE TRIGGER trg_update_remaining_advance_upd
    AFTER UPDATE OF advance, advance_deduction ON payments
    BEGIN
        UPDATE payments
        SET remaining_advance = NEW.advance - NEW.advance_deduction,
            payment_after_deduction = NEW.payment - NEW.advance_deduction
        WHERE id = NEW.id;
    END;
    """
    cur.executescript(triggers)

    # ------------------------------
    # 5. Schema migration
    # ------------------------------
    migrate_local_db(conn)

    # ------------------------------
    # 6. Demo client/user handling
    # ------------------------------
    # ❌ REMOVE the hardcoded insert
    # ✅ Instead, just leave a placeholder for cloud sync
    print("ℹ️ Skipping local demo client/user creation. Expecting cloud sync to populate them.")

    # ------------------------------
    # 7. Commit & close
    # ------------------------------
    conn.commit()
    conn.close()
    print(f"✅ Database initialized at: {DB_PATH} with tables, triggers, demo client/admin.")
