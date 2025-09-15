import sqlite3
from database import insert_into_local, get_conn
from supabase import create_client, Client
from datetime import datetime
import threading
import time

# -----------------------------
# Supabase client
# -----------------------------
SUPABASE_URL = "https://jjzxnguvnlfvxljyqiye.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImpqenhuZ3V2bmxmdnhsanlxaXllIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTY2Mjk0NDksImV4cCI6MjA3MjIwNTQ0OX0.f7hCWxUdwTIUotskNjAtKIo-Tae7LCYZpiGowZvpAL0"
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# -----------------------------
# Local SQLite
# -----------------------------
DB_PATH = "labor.db"

def get_sqlite_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

# -----------------------------
# Tables to sync
# -----------------------------
CLIENT_TABLES = [
    "clients",
    "users",
    "sites",
    "labors",
    "business_info",
    "site_assignments",
    "attendance",
    "payments",
    "site_materials",
    "site_expenses",
    "licenses",                # 🔥 add this
    "subscription_payments",   # 🔥 add this
]

GLOBAL_TABLES = ["plans"]

# -----------------------------
# Demo mode global flag
# -----------------------------
IS_DEMO_MODE = False

def set_demo_mode(flag: bool):
    global IS_DEMO_MODE
    IS_DEMO_MODE = flag

# -----------------------------
# Utility: check if uuid is usable on Supabase
# -----------------------------
supabase_uuid_cache = {}

def supabase_has_uuid_unique(table):
    if table in supabase_uuid_cache:
        return supabase_uuid_cache[table]
    try:
        resp = supabase.table(table).select("uuid").limit(1).execute()
        if resp.data and "uuid" in resp.data[0]:
            supabase_uuid_cache[table] = True
            return True
    except Exception:
        pass
    supabase_uuid_cache[table] = False
    return False


# -----------------------------
# Reset local DB (demo/paid)
# -----------------------------
def reset_local_db():
    """
    Wipes demo/local data from SQLite before full sync for paid clients.
    """
    conn = get_sqlite_conn()
    cur = conn.cursor()
    try:
        # Check if is_demo column exists before deleting
        cur.execute("PRAGMA table_info(clients)")
        cols = [c[1] for c in cur.fetchall()]
        if "is_demo" in cols:
            for table in ["clients", "users", "sites", "labors", "business_info",
                          "site_assignments", "attendance", "payments",
                          "site_materials", "site_expenses","licenses","subscription_payments"]:
                cur.execute(f"DELETE FROM {table} WHERE is_demo = 0")
            conn.commit()
            print("✅ Local DB reset completed")
        else:
            print("⚠️ 'is_demo' column not found, skipping reset")
    except Exception as e:
        print(f"⚠️ Error resetting local DB: {e}")
    finally:
        conn.close()

# -----------------------------
# Push local → cloud
# -----------------------------
def push_table(table, client_id=None):
    if IS_DEMO_MODE:
        print(f"⏸️ Skipping push for demo client ({client_id}) - table {table}")
        return

    conn = get_sqlite_conn()
    cur = conn.cursor()
    if client_id:
        cur.execute(f"SELECT * FROM {table} WHERE sync_status='pending' AND client_id=?", (client_id,))
    else:
        cur.execute(f"SELECT * FROM {table} WHERE sync_status='pending'")
    rows = cur.fetchall()
    colnames = [desc[0] for desc in cur.description]

    for row in rows:
        row_dict = dict(zip(colnames, row))
        row_copy = dict(row_dict)
        row_copy.pop("sync_status", None)

        try:
            if supabase_has_uuid_unique(table):
                supabase.table(table).upsert(row_copy, on_conflict=["uuid"]).execute()
            else:
                supabase.table(table).insert(row_copy).execute()
            cur.execute(f"UPDATE {table} SET sync_status='synced' WHERE uuid=?", (row_dict.get("uuid"),))
        except Exception as e:
            print(f"⚠️ Push error in {table}: {e}")

    conn.commit()
    conn.close()

# -----------------------------
# Pull cloud → local
# -----------------------------
def pull_table(table, client_id=None):
    conn = get_sqlite_conn()
    cur = conn.cursor()
    try:
        # --- Clients table ---
        if table == "clients":
            if client_id is not None:
                # ✅ Pull only this client
                resp = supabase.table(table).select("*").eq("client_id", client_id).execute()
            else:
                # ✅ Only pull demo clients (never all paid)
                resp = supabase.table(table).select("*").eq("is_demo", True).execute()

        # --- Users table ---
        elif table == "users":
            if client_id is not None:
                # ✅ Pull only users for this client
                resp = supabase.table(table).select("*").eq("client_id", client_id).execute()
            else:
                # ✅ Only demo users
                resp = supabase.table(table).select("*").eq("client_id", 0).execute()

        # --- Other tables (attendance, payments, etc.) ---
        elif client_id is not None:
            resp = supabase.table(table).select("*").eq("client_id", client_id).execute()
        else:
            # Global tables (plans, etc.)
            resp = supabase.table(table).select("*").execute()

        # --- Insert into local SQLite ---
        for row in resp.data:
            if "uuid" in row:
                placeholders = ",".join(["?"] * len(row))
                columns = ",".join(row.keys())
                update_clause = ",".join([f"{col}=excluded.{col}" for col in row.keys()])
                sql = f"""
                    INSERT INTO {table} ({columns})
                    VALUES ({placeholders})
                    ON CONFLICT(uuid) DO UPDATE SET {update_clause};
                """
                cur.execute(sql, tuple(row.values()))
            else:
                placeholders = ",".join(["?"] * len(row))
                columns = ",".join(row.keys())
                sql = f"INSERT OR IGNORE INTO {table} ({columns}) VALUES ({placeholders})"
                cur.execute(sql, tuple(row.values()))

        print(f"[PULL] {table} → {len(resp.data)} rows for client_id={client_id}")

    except Exception as e:
        print(f"⚠️ Pull error in {table}: {e}")
    conn.commit()
    conn.close()

# -----------------------------
# Full sync for one client
# -----------------------------
def full_sync(client_id, push_globals=False):
    print(f"🔄 Starting full sync for client {client_id} (Demo={IS_DEMO_MODE})...")

    if IS_DEMO_MODE:
        # ✅ Demo: load special demo dataset
        load_demo_from_cloud(client_id)
        print(f"✅ Demo full sync completed for client {client_id}")
        return

    # --- Normal (paid) client sync ---
    for table in CLIENT_TABLES:
        # 🚫 Never pull clients/users without a filter
        if table in ["clients", "users"]:
            push_table(table, client_id)
            pull_table(table, client_id)   # ✅ filtered only
        else:
            push_table(table, client_id)
            pull_table(table, client_id)

    # Push globals (plans etc.) only if needed
    if push_globals:
        for table in GLOBAL_TABLES:
            push_table(table, None)

    # ✅ Always pull global tables (safe without filter)
    for table in GLOBAL_TABLES:
        pull_table(table, None)

    print(f"✅ Full sync completed for client {client_id}")

# -----------------------------
# Continuous sync (per client)
# -----------------------------
def continuous_sync(stop_event, client_id, interval=30, push_globals=False):
    while not stop_event.is_set():
        try:
            full_sync(client_id, push_globals=push_globals)
        except Exception as e:
            print(f"⚠️ Sync error for client {client_id}: {e}")
        stop_event.wait(interval)


def get_table_columns(table):
    conn = get_sqlite_conn()
    cur = conn.cursor()
    cur.execute(f"PRAGMA table_info({table})")
    cols = [info[1] for info in cur.fetchall()]  # info[1] is column name
    conn.close()
    print(f"[DEBUG] Columns for {table}: {cols}")
    return cols

# -----------------------------
# Load only demo client & its users
# -----------------------------
def load_demo_from_cloud(client_id: int):
    """
    Pulls demo client, its users, licenses, subscription payments,
    and global plans table from cloud into local DB.
    Demo data is never pushed back to cloud.
    """
    if supabase is None:
        print("⚠️ Supabase not initialized, skipping demo load")
        return

    print(f"[SYNC] Loading demo client {client_id} from cloud...")
    conn = get_conn()

    try:
        # --- fetch demo client ---
        client_resp = supabase.table("clients").select("*").eq("client_id", client_id).eq("is_demo", True).execute()
        if client_resp.data:
            for row in client_resp.data:
                insert_into_local(conn, "clients", row)

        # --- fetch users linked to this demo client ---
        users_resp = supabase.table("users").select("*").eq("client_id", client_id).execute()
        if users_resp.data:
            for row in users_resp.data:
                insert_into_local(conn, "users", row)

        # --- fetch licenses linked to this demo client ---
        licenses_resp = supabase.table("licenses").select("*").eq("client_id", client_id).execute()
        if licenses_resp.data:
            for row in licenses_resp.data:
                insert_into_local(conn, "licenses", row)

        # --- fetch subscription payments linked to this demo client ---
        subs_resp = supabase.table("subscription_payments").select("*").eq("client_id", client_id).execute()
        if subs_resp.data:
            for row in subs_resp.data:
                insert_into_local(conn, "subscription_payments", row)

        # --- fetch global plans (shared for all clients) ---
        plans_resp = supabase.table("plans").select("*").execute()
        if plans_resp.data:
            for row in plans_resp.data:
                insert_into_local(conn, "plans", row)

        print("[SYNC] Demo client, users, licenses, subscription_payments, and plans loaded locally (not syncing to cloud).")

    except Exception as e:
        print(f"⚠️ Demo client load failed: {e}")
    finally:
        conn.close()



# -----------------------------
# Load single client (demo or paid) from cloud
# -----------------------------
def load_client_from_cloud(client_id: int):
    """
    Pulls only the requested client_id (demo or paid) and its users into local DB.
    Does NOT pull other clients.
    """
    global IS_DEMO_MODE
    IS_DEMO_MODE = (client_id == 0)  # demo mode if id=0

    if supabase is None:
        print("⚠️ Supabase not initialized, skipping client load")
        return

    print(f"[SYNC] Loading client {client_id} from cloud (Demo={IS_DEMO_MODE})...")
    conn = get_conn()

    try:
        # --- Load client row ---
        client_resp = supabase.table("clients").select("*").eq("client_id", client_id).execute()
        if client_resp.data:
            for row in client_resp.data:
                insert_into_local(conn, "clients", row)
            print(f"✅ Client {client_id} loaded locally")

        # --- Load users for this client ---
        users_resp = supabase.table("users").select("*").eq("client_id", client_id).execute()
        if users_resp.data:
            for row in users_resp.data:
                insert_into_local(conn, "users", row)
            print(f"✅ Users for client {client_id} loaded locally")

    except Exception as e:
        print(f"⚠️ Error loading client {client_id} from cloud: {e}")
    finally:
        conn.close()

# -----------------------------
# Start sync for a client from Flask
# -----------------------------
def start_sync(client_id, interval=30, push_globals=False):
    stop_event = threading.Event()
    thread = threading.Thread(
        target=continuous_sync,
        args=(stop_event, client_id, interval, push_globals),
        daemon=True
    )
    thread.start()
    print(f"🚀 Background sync started for client_id={client_id}")
    return stop_event, thread


# -----------------------------
# Multi-client thread starter
# -----------------------------
if __name__ == "__main__":
    active_clients = supabase.table("clients").select("client_id").eq("is_active", True).execute().data or []
    client_ids = [c["client_id"] for c in active_clients]

    stop_events, threads = {}, {}
    for i, cid in enumerate(client_ids):
        stop_events[cid] = threading.Event()
        push_globals = (i == 0)  # only first thread pushes global tables
        threads[cid] = threading.Thread(target=continuous_sync, args=(stop_events[cid], cid, 30, push_globals))
        threads[cid].start()
        print(f"🚀 Started continuous sync for client_id={cid} (push_globals={push_globals})")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("🛑 Stopping all sync threads...")
        for cid in client_ids:
            stop_events[cid].set()
        for cid in client_ids:
            threads[cid].join()
