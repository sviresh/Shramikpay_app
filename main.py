# Top of main.py (with other imports)
from database import init_db
import os
from database import init_db, migrate_local_db, get_conn, insert_into_local
from database import insert_into_local, get_conn
import sqlite3
import threading  # << Add this
from datetime import datetime
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.security import check_password_hash, generate_password_hash
from functools import wraps
import webview  # <-- Add this at the top with other imports
from database import get_db, get_conn, init_db, close_db
from flask import send_from_directory
import io
import csv
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, jsonify, Response, session
from datetime import datetime, date, timedelta
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from flask import Flask, request, jsonify, Response
import sqlite3
import csv
import io
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
import webview
import threading
import os  # also make sure os is imported, since you use it for paths
from flask import send_from_directory
from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import check_password_hash
from database import get_db, get_conn, init_db, close_db
from datetime import datetime  # at top of your file
from datetime import datetime, timedelta  # at the top of your file
import razorpay   # ✅ this fixes NameError
from database import init_db, get_db, close_db
from supabase import create_client

import sys, os
from flask import Flask

if getattr(sys, 'frozen', False):
    # Running in EXE
    template_folder = os.path.join(sys._MEIPASS, "templates")
    static_folder = os.path.join(sys._MEIPASS, "static")
else:
    # Running in PyCharm
    template_folder = "templates"
    static_folder = "static"

app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)

# ------------------------------
# Initialize DB at startup
# ------------------------------
init_db()  # ensures tables exist and demo client/admin created



SUPABASE_URL = "https://jjzxnguvnlfvxljyqiye.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImpqenhuZ3V2bmxmdnhsanlxaXllIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTY2Mjk0NDksImV4cCI6MjA3MjIwNTQ0OX0.f7hCWxUdwTIUotskNjAtKIo-Tae7LCYZpiGowZvpAL0"
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)



# ------------------------------
#  Migrate local DB (add missing columns if any)
# ------------------------------
conn = get_conn()
try:
    migrate_local_db(conn)
    print("✅ Local DB migration completed. 'is_demo' and other columns ensured.")
finally:
    conn.close()

# ------------------------------
# 3️⃣ Safe insert wrapper
# ------------------------------
def insert_local(table, row):
    """Insert a row dict into a table safely."""
    conn = get_conn()
    try:
        insert_into_local(conn, table, row)
    finally:
        conn.close()

# ------------------------------
# 4️⃣ Load demo clients/users from Supabase
# ------------------------------
def sync_demo_clients():
    try:
        # Fetch all demo clients from Supabase where is_demo=1
        demo_clients = supabase.table("clients").select("*").eq("is_demo", 1).execute()
        for client in demo_clients.data:
            insert_local("clients", client)
        print(f"✅ Loaded {len(demo_clients.data)} demo clients from cloud.")
    except Exception as e:
        print(f"⚠️ Error loading demo clients from cloud: {e}")

def sync_demo_users():
    try:
        # Fetch all users linked to demo clients
        demo_users = supabase.table("users").select("*").eq("is_demo", 1).execute()
        for user in demo_users.data:
            insert_local("users", user)
        print(f"✅ Loaded {len(demo_users.data)} demo users from cloud.")
    except Exception as e:
        print(f"⚠️ Error loading demo users from cloud: {e}")

# ------------------------------
# 5️⃣ Run demo/cloud sync
# ------------------------------
print("ℹ️ Syncing demo clients/users from cloud...")
sync_demo_clients()
sync_demo_users()

# ------------------------------
# 6️⃣ Start the app
# ------------------------------
print("🚀 Starting application...")


# ------------------------------
# Flask Setup
# ------------------------------
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "supersecretkey")
app.teardown_appcontext(close_db)

# ------------------------------
# Login Required Decorator
# ------------------------------
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated

from datetime import datetime, date

def license_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))

        db = get_db()
        user = db.execute(
            "SELECT license_expiry FROM clients WHERE id = ?", (session["client_id"],)
        ).fetchone()

        if not user or not user["license_expiry"]:
            return redirect(url_for("upgrade"))

        # Convert string -> date
        expiry = None
        try:
            expiry = datetime.strptime(user["license_expiry"], "%Y-%m-%d").date()
        except Exception:
            pass

        if not expiry or expiry < date.today():
            if request.endpoint != "upgrade":  # avoid loop
                return redirect(url_for("upgrade"))

        return f(*args, **kwargs)
    return decorated


# ------------------------------
# Login Route
# ------------------------------
from flask import Flask, render_template, request, redirect, url_for, flash, session
from werkzeug.security import check_password_hash
from datetime import datetime, timedelta
from dateutil import parser

from sync_manager import (
    load_demo_from_cloud,
    reset_local_db,
    full_sync,
    set_demo_mode,
    start_sync,   # <-- add this
)


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        client_code = request.form.get("client_code", "").strip().upper()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        db = get_db()
        today = datetime.now().date()

        # -------------------------------
        # Identify demo vs paid client
        # -------------------------------
        is_demo_client = client_code == "DEM25-00002"

        try:
            if is_demo_client:
                # -------------------------------
                # Demo client flow
                # -------------------------------
                set_demo_mode(True)
                reset_local_db()
                load_demo_from_cloud(0)  # demo client_id = 0

                client = db.execute(
                    "SELECT * FROM clients WHERE client_code = ?", (client_code,)
                ).fetchone()
                if not client:
                    flash("Demo client not found", "danger")
                    return redirect(url_for("login"))

                client_id = client["client_id"]
                user = db.execute(
                    "SELECT * FROM users WHERE username = ? AND client_id = ?",
                    (username, client_id)
                ).fetchone()

                if not user or not check_password_hash(user["password"], password):
                    flash("Invalid username or password", "danger")
                    return redirect(url_for("login"))

                session["user_id"] = user["id"]
                session["client_id"] = client_id
                session["role"] = user["role"]

                # Demo expiry
                sub_end = client["subscription_end"]
                if sub_end:
                    demo_end = parser.parse(sub_end).date()
                else:
                    start = parser.parse(client["subscription_start"]).date()
                    demo_end = start + timedelta(days=client["demo_days"] or 30)

                if today > demo_end:
                    flash("Your demo has expired. Please upgrade.", "warning")
                    return redirect(url_for("upgrade"))

                flash(f"Demo active until {demo_end}", "success")
                return redirect(url_for("dashboard"))

            else:
                # -------------------------------
                # Paid client flow
                # -------------------------------
                set_demo_mode(False)

                # Pull client & users from cloud BEFORE local sync
                client_resp = supabase.table("clients").select("*").eq("client_code", client_code).execute()
                if not client_resp.data:
                    flash("Paid client not found", "danger")
                    return redirect(url_for("login"))

                client_data = client_resp.data[0]
                insert_into_local(get_conn(), "clients", client_data)
                client_id = client_data["client_id"]

                # Pull users for this client
                users_resp = supabase.table("users").select("*").eq("client_id", client_id).execute()
                if users_resp.data:
                    for row in users_resp.data:
                        insert_into_local(get_conn(), "users", row)

                # Fetch local client & user
                client = db.execute("SELECT * FROM clients WHERE client_code = ?", (client_code,)).fetchone()
                user = db.execute(
                    "SELECT * FROM users WHERE username = ? AND client_id = ?",
                    (username, client_id)
                ).fetchone()

                if not user or not check_password_hash(user["password"], password):
                    flash("Invalid username or password", "danger")
                    return redirect(url_for("login"))

                session["user_id"] = user["id"]
                session["client_id"] = client_id
                session["role"] = user["role"]

                # Start background sync safely (local DB already has client/users)
                start_sync(client_id)
                full_sync(client_id, push_globals=False)

                # License check
                if client["license_expiry"]:
                    expiry_date = datetime.strptime(client["license_expiry"], "%Y-%m-%d").date()
                    if not (today <= expiry_date and client["is_active"]):
                        flash("Your license has expired or is inactive.", "warning")
                        return redirect(url_for("upgrade"))

                return redirect(url_for("dashboard"))

        except Exception as e:
            print(f"⚠️ Login error: {e}")
            flash("An error occurred during login. Please contact support.", "danger")
            return redirect(url_for("login"))

    # Always return login page on GET
    return render_template("login.html")




@app.route("/upgrade")
@login_required
def upgrade():
    db = get_db()
    rows = db.execute("""
        SELECT id, name, sites,users_per_site, yearly_price, monthly_price, notes, active_offer, offer_price, updated_at
        FROM plans
        ORDER BY updated_at DESC
    """).fetchall()
    plans = [dict(row) for row in rows]
    return render_template("upgrade.html", plans=plans)



# --- Razorpay client (Test Keys) ---
razorpay_client = razorpay.Client(auth=("rzp_test_RF2YJr33gsxQkz", "d1KzutkuiIVxce4d7gYNaFpN"))

# --- Create Razorpay order ---
@app.route("/pay", methods=["POST"])
@login_required
def pay_post():
    client_id = session["client_id"]   # take from logged-in user
    plan_id = request.form.get("plan_id")
    plan_type = request.form.get("billing_cycle")

    return redirect(url_for("pay_get", client_id=client_id, plan_id=plan_id, plan_type=plan_type))


@app.route("/pay/<client_id>/<plan_id>/<plan_type>")
@login_required
def pay_get(client_id, plan_id, plan_type):
    db = get_db()
    plan = db.execute("SELECT monthly_price, yearly_price FROM plans WHERE id=?", (plan_id,)).fetchone()
    db.close()

    if not plan:
        return "Plan not found", 404

    amount = plan["monthly_price"] if plan_type.lower() == "monthly" else plan["yearly_price"]

    order = razorpay_client.order.create({
        "amount": amount * 100,   # paise
        "currency": "INR",
        "payment_capture": 1
    })
    order_id = order["id"]

    return f"""
    <h2>Pay with Razorpay</h2>
    <button id="rzp-button">Pay Now</button>
    <script src="https://checkout.razorpay.com/v1/checkout.js"></script>
    <script>
        var options = {{
            "key": "rzp_test_RF2YJr33gsxQkz",
            "amount": "{amount*100}",
            "currency": "INR",
            "name": "Labor Management",
            "description": "Subscription Plan Payment",
            "order_id": "{order_id}",
            "handler": function (response) {{
                fetch("/confirm_payment", {{
                    method: "POST",
                    headers: {{ "Content-Type": "application/json" }},
                    body: JSON.stringify({{
                        client_id: "{client_id}",
                        plan_id: "{plan_id}",
                        plan_type: "{plan_type}",
                        amount: {amount},
                        razorpay_payment_id: response.razorpay_payment_id,
                        razorpay_order_id: response.razorpay_order_id,
                        razorpay_signature: response.razorpay_signature
                    }})
                }}).then(r => r.json()).then(d => {{
                    alert("Payment Successful! License till " + d.license_end);
                }});
            }},
            "theme": {{
                "color": "#3399cc"
            }}
        }};
        var rzp1 = new Razorpay(options);
        document.getElementById("rzp-button").onclick = function(e){{
            rzp1.open();
            e.preventDefault();
        }}
    </script>
    """


# ------------------------------
# Labor Register Route
# ------------------------------
@app.route("/labor_register", methods=["GET"])
@login_required
def labor_register_screen():
    return render_template("LaborRegisterScreen.html")


from datetime import datetime, timedelta

@app.route("/dashboard")
@login_required
def dashboard():
    db = get_db()
    user_id = session["user_id"]

    client = db.execute("SELECT * FROM clients WHERE client_id = ?", (user_id,)).fetchone()

    if client:
        if client["is_demo"]:
            # calculate demo expiry based on subscription_start + demo_days
            start = client["subscription_start"]
            if start:
                demo_start = datetime.fromisoformat(start)
                demo_expiry = demo_start + timedelta(days=client["demo_days"])
                if datetime.now() > demo_expiry:
                    # demo expired → redirect to upgrade
                    return redirect(url_for("upgrade"))
            else:
                # no start date, assume demo just started
                db.execute(
                    "UPDATE clients SET subscription_start = ? WHERE id = ?",
                    (datetime.now().isoformat(), user_id)
                )
                db.commit()

    # demo still valid or paid user → normal dashboard
    return redirect(url_for("labor_register_screen"))


@app.route("/")
def home():
    if "user_id" in session:
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))

# ------------------------------
# Logout Route
# ------------------------------
@app.route("/logout")
def logout():
    stop_sync()  # 👈 stop sync when user logs out
    session.clear()
    return redirect(url_for("login"))

# ------------------------------
# Forgot Password Route
# ------------------------------
@app.route('/forgot_password', methods=["GET", "POST"])
def forgot_password():
    if "user_id" in session:
        return redirect(url_for("labor_register_screen"))

    error = None
    success = None

    if request.method == "POST":
        username = request.form.get("username")
        new_password = request.form.get("new_password")
        confirm_password = request.form.get("confirm_password")

        if not username or not new_password or not confirm_password:
            error = "All fields are required."
        elif new_password != confirm_password:
            error = "Passwords do not match."
        else:
            hashed_pw = generate_password_hash(new_password)
            conn = get_db()
            cur = conn.cursor()
            cur.execute("SELECT * FROM users WHERE username=?", (username,))
            user = cur.fetchone()
            if not user:
                error = "Username not found."
            else:
                cur.execute("UPDATE users SET password=? WHERE username=?", (hashed_pw, username))
                conn.commit()
                success = "✅ Password updated successfully!"
            conn.close()

    return render_template("ForgotPassword.html", error=error, success=success)

# ------------------------------
# Get Session Info Route
# ------------------------------
@app.route("/get_session")
@login_required
def get_session():
    return jsonify({
        "user_id": session.get("user_id"),
        "client_id": session.get("client_id"),
        "role": session.get("role")
    })

@app.route("/labor_register")
@login_required
def labor_register():
    user_id = session.get("user_id")
    role = session.get("role")
    client_id = session.get("client_id")

    db = get_db()
    cur = db.cursor()

    # Fetch allowed sites
    if role == "admin":
        cur.execute("SELECT id, name FROM sites WHERE client_id=? AND is_active=1 ORDER BY name", (client_id,))
    else:
        site_ids = get_user_site_filter(user_id, role)
        if site_ids:
            placeholders = ",".join(["?"] * len(site_ids))
            cur.execute(f"SELECT id, name FROM sites WHERE client_id=? AND id IN ({placeholders}) AND is_active=1 ORDER BY name", [client_id]+site_ids)
        else:
            sites = []
    sites = cur.fetchall() or []

    return render_template("LaborRegister.html", sites=sites)


# ------------------------------
# Attendance Page
# ------------------------------
@app.route("/attendance", methods=["GET"])
@login_required
def attendance():
    user_id = session.get("user_id")
    role = session.get("role")
    client_id = session.get("client_id")

    db = get_db()
    db.row_factory = sqlite3.Row  # ✅ Make fetchall return dict-like rows
    cur = db.cursor()

    # Allowed site IDs
    site_ids = get_user_site_filter(user_id, role)

    # Fetch sites
    if role == "admin":
        cur.execute("SELECT id, name FROM sites WHERE client_id=? AND is_active=1 ORDER BY name", (client_id,))
    else:
        if not site_ids:
            return render_template("AttendanceScreen.html", labors=[], attendance_dict={}, sites=[], current_site_id=None, current_start=None, role=role)
        placeholders = ",".join(["?"] * len(site_ids))
        cur.execute(f"SELECT id, name FROM sites WHERE client_id=? AND is_active=1 AND id IN ({placeholders}) ORDER BY name", [client_id]+site_ids)
    sites = [dict(s) for s in cur.fetchall()]  # convert to list of dicts

    # Determine current site
    site_id = request.args.get("site_id", type=int)
    if not site_id and sites:
        site_id = sites[0]["id"]

    # Security check for engineer
    if role != "admin" and site_ids is not None and site_id not in site_ids:
        return render_template("AttendanceScreen.html", labors=[], attendance_dict={}, sites=sites, current_site_id=None, current_start=None, role=role)

    # Fetch labors in this site
    cur.execute("SELECT id, name, site_id FROM labors WHERE client_id=? AND site_id=? ORDER BY name", (client_id, site_id))
    labors = [dict(l) for l in cur.fetchall()]  # convert to dicts

    # Week start
    start_param = request.args.get("start")
    today = date.today()
    week_start = datetime.strptime(start_param, "%Y-%m-%d").date() if start_param else today - timedelta(days=today.weekday())
    week_start_str = week_start.isoformat()

    # Attendance
    labor_ids = [l["id"] for l in labors]
    attendance_dict = {}
    if labor_ids:
        placeholders = ",".join(["?"] * len(labor_ids))
        cur.execute(f"SELECT labor_id, day, status, extra_hours FROM attendance WHERE site_id=? AND week_start=? AND labor_id IN ({placeholders})", [site_id, week_start_str]+labor_ids)
        for row in cur.fetchall():
            attendance_dict.setdefault(row["labor_id"], {})[row["day"]] = {"status": row["status"] or "", "extra_hours": row["extra_hours"] or 0}

    return render_template(
        "AttendanceScreen.html",
        labors=labors,
        attendance_dict=attendance_dict,
        sites=sites,
        current_site_id=site_id,
        current_start=week_start_str,
        role=role
    )


@app.route("/get_attendance", methods=["GET"])
@login_required
def get_attendance():
    user_id = session.get("user_id")
    role = session.get("role")
    site_ids = get_user_site_filter(user_id, role)

    site_id = request.args.get("site_id", type=int)
    week_start = request.args.get("week_start")

    if not site_id or not week_start:
        return jsonify({"success": False, "message": "Missing site_id or week_start"}), 400

    # ✅ Engineer cannot request unassigned site
    if site_ids is not None and site_id not in site_ids:
        return jsonify({"success": False, "message": "Access denied for this site"}), 403

    conn = get_db()
    cur = conn.cursor()
    cur.execute("""
        SELECT labor_id, day, status, extra_hours
        FROM attendance
        WHERE client_id=? AND site_id=? AND week_start=?
    """, (session["client_id"], site_id, week_start))
    rows = cur.fetchall()
    conn.close()

    result = {}
    for lid, day, status, extra in rows:
        if lid not in result:
            result[lid] = {}
        result[lid][day] = {"status": status, "extra_hours": extra}

    return jsonify({"success": True, "attendance": result})


@app.route("/site_material", methods=["GET"])
def site_material():
    # Render your Site Material page
    return render_template("SiteMaterialScreen.html")

@app.route("/site_expenses", methods=["GET"])
def site_expenses():
    # Render your Site Expenses page
    return render_template("SiteExpensesScreen.html")

@app.route('/setup_site')
def setup_site():
    return render_template('setup_site.html')



@app.route("/reports", methods=["GET"])
def reports():
    # Render your Reports page
    return render_template("ReportScreen.html")



def get_labor_id(labor_name):
    conn = get_db()


    cur = conn.cursor()
    cur.execute("SELECT id FROM labors WHERE name = ?", (labor_name,))
    row = cur.fetchone()
    conn.close()
    if row:
        return row["id"]  # SQLite Row object
    return None

# ---------------------- /save_attendance ----------------------
from flask import request, session, jsonify
import sqlite3
from flask import request, session, jsonify

from datetime import datetime, timedelta
from flask import request, session, jsonify
import sqlite3

@app.route("/save_attendance", methods=["POST"])
@login_required
def save_attendance():
    if "client_id" not in session:
        return jsonify({"success": False, "message": "Unauthorized"}), 401

    client_id = session["client_id"]
    user_id = session.get("user_id")
    role = session.get("role")
    data = request.json  # frontend sends array of rows

    conn = sqlite3.connect("labor.db", timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        for row in data:
            site_id = row.get("site_id")
            labor_id = row.get("labor_id")
            week_start = row.get("week_start")   # e.g., "2025-09-28"
            days = row.get("days", {})            # { "Sun": {...}, "Mon": {...} } or { "2025-09-28": {...}, ... }

            if not (site_id and labor_id and week_start):
                continue

            # Convert week_start to date object
            week_start_date = datetime.strptime(week_start, "%Y-%m-%d").date()

            # Auto-assign engineer if role=engineer
            if role == "engineer":
                cursor.execute("""
                    INSERT OR IGNORE INTO site_assignments (user_id, client_id, site_id, assigned_at)
                    VALUES (?, ?, ?, CURRENT_TIMESTAMP)
                """, (user_id, client_id, site_id))
                conn.commit()

            # Define weekday order
            weekday_order = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]

            for day_key, info in days.items():
                if not info:
                    continue

                # Determine if frontend sent a date or day name
                try:
                    # Try parsing as actual date
                    day_date = datetime.strptime(day_key, "%Y-%m-%d").date()
                except ValueError:
                    # Otherwise, assume it's a day name, calculate offset from week_start
                    if day_key not in weekday_order:
                        continue  # skip invalid keys
                    offset = (weekday_order.index(day_key) - week_start_date.weekday()) % 7
                    day_date = week_start_date + timedelta(days=offset)

                day_str = day_date.isoformat()  # YYYY-MM-DD

                status = info.get("status", "")
                extra_hours = float(info.get("extra_hours", 0))

                cursor.execute("""
                    INSERT INTO attendance (client_id, site_id, labor_id, week_start, day, status, extra_hours)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(client_id, labor_id, site_id, week_start, day)
                    DO UPDATE SET
                        status = CASE
                            WHEN excluded.status IS NOT NULL AND excluded.status != ''
                            THEN excluded.status
                            ELSE attendance.status
                        END,
                        extra_hours = excluded.extra_hours
                """, (client_id, site_id, labor_id, week_start, day_str, status, extra_hours))

            # Recalculate total_hours for payments
            cursor.execute("""
                SELECT SUM(
                    CASE status WHEN 'FD' THEN 8 WHEN 'HD' THEN 4 ELSE 0 END + extra_hours
                ) as total
                FROM attendance
                WHERE client_id=? AND site_id=? AND labor_id=? AND week_start=?
            """, (client_id, site_id, labor_id, week_start))
            total_hours = cursor.fetchone()["total"] or 0

            # Update payments
            cursor.execute("""
                INSERT INTO payments (client_id, labor_id, site_id, week_start, total_hours)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(client_id, labor_id, site_id, week_start)
                DO UPDATE SET total_hours=excluded.total_hours
            """, (client_id, labor_id, site_id, week_start, total_hours))

        conn.commit()
        return jsonify({"success": True, "message": "Attendance and payments updated successfully!"})

    except Exception as e:
        conn.rollback()
        import traceback; traceback.print_exc()
        return jsonify({"success": False, "message": str(e)})
    finally:
        conn.close()

# ---------------------- /update_extra_hours ----------------------
@app.route("/update_extra_hours", methods=["POST"])
@login_required
def update_extra_hours():
    try:
        data = request.get_json(force=True)
        labor_id = data.get("labor_id")
        week_start = data.get("week_start")
        day = data.get("day")
        site_id = data.get("site_id")
        extra_hours = float(data.get("extra_hours") or 0)
        client_id = session["client_id"]  # include client_id for conflict check

        conn = get_db()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO attendance (client_id, site_id, labor_id, week_start, day, status, extra_hours)
            VALUES (?, ?, ?, ?, ?, '', ?)
            ON CONFLICT(client_id, labor_id, site_id, week_start, day)
            DO UPDATE SET
                extra_hours = excluded.extra_hours
        """, (client_id, site_id, labor_id, week_start, day, extra_hours))

        conn.commit()
        conn.close()
        return jsonify({"success": True, "message": "Extra hours updated successfully!"})

    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/update_labor_attendance", methods=["POST"])
def update_labor_attendance():
    data = request.get_json()
    if not data:
        return jsonify({"success": False, "message": "Empty JSON payload"}), 400

    # Normalize to list
    if isinstance(data, dict):
        data = [data]
    elif not isinstance(data, list):
        return jsonify({"success": False, "message": "Invalid JSON format"}), 400

    conn = get_db()

    try:
        cur = conn.cursor()

        for record in data:
            labor_id = record.get("labor_id")
            week_start = record.get("week_start")
            days = record.get("days", {})

            if not labor_id or not week_start or not days:
                return jsonify({
                    "success": False,
                    "message": "Missing labor_id, week_start, or days"
                }), 400

            for day, info in days.items():
                status = info.get("status", "")
                try:
                    extra_hours = float(info.get("extra_hours", 0))
                except (ValueError, TypeError):
                    extra_hours = 0

                # First check if record exists
                cur.execute("""
                    SELECT status, extra_hours 
                    FROM attendance
                    WHERE labor_id=? AND week_start=? AND day=?
                """, (labor_id, week_start, day))
                row = cur.fetchone()

                if row:
                    # Keep existing + add new hours
                    existing_status, existing_extra = row
                    new_extra = existing_extra + extra_hours
                    cur.execute("""
                        UPDATE attendance
                        SET status=?, extra_hours=?
                        WHERE labor_id=? AND week_start=? AND day=?
                    """, (status or existing_status, new_extra, labor_id, week_start, day))
                else:
                    # Insert if not exists
                    cur.execute("""
                        INSERT INTO attendance (labor_id, week_start, day, status, extra_hours)
                        VALUES (?, ?, ?, ?, ?)
                    """, (labor_id, week_start, day, status, extra_hours))

            # Recalculate payment once per labor per week
            calculate_and_update_payment(labor_id, week_start, conn)

        conn.commit()
        return jsonify({"success": True, "message": "Attendance updated successfully!"})

    except Exception as e:
        conn.rollback()
        return jsonify({"success": False, "message": str(e)}), 500
    finally:
        conn.close()

@app.route("/payment", methods=["GET"])
@login_required
def payment_screen():
    user_id = session.get("user_id")
    role = session.get("role")
    client_id = session.get("client_id")

    conn = get_db()
    cur = conn.cursor()

    # Fetch labor list
    labors = cur.execute("SELECT id, name FROM labors ORDER BY name").fetchall()

    # Fetch latest payment entries per labor
    rows = cur.execute("""
        SELECT p.*, l.name AS labor_name
        FROM payments p
        JOIN labors l ON l.id = p.labor_id
        WHERE (p.labor_id, p.week_start) IN (
            SELECT labor_id, MAX(week_start)
            FROM payments
            WHERE client_id = ?
            GROUP BY labor_id
        )
        ORDER BY l.name
    """, (client_id,)).fetchall()

    payments = {row["labor_id"]: dict(row) for row in rows}

    # Get sites user can access
    site_ids = get_user_site_filter(user_id, role)
    if not site_ids:
        site_ids = []

    conn.close()

    return render_template(
        "PaymentScreen.html",
        labors=labors,
        payments=payments,
        site_ids=site_ids  # ✅ Pass this to template
    )


# ---------------- Save payments ----------------

@app.route("/save_payment", methods=["POST"])
@login_required
def save_payment():
    try:
        data = request.get_json()
        payments = data.get("payments", [])
        if not payments:
            return jsonify({"success": False, "error": "No payment data"}), 400

        user_id = session.get("user_id")
        role = session.get("role")
        site_ids = get_user_site_filter(user_id, role) or []

        conn = get_db()
        cur = conn.cursor()
        client_id = session.get("client_id")
        if not client_id:
            return jsonify({"success": False, "error": "Client not found"}), 400

        saved_count = 0
        skipped_sites = []

        for p in payments:
            labor_id = p.get("labor_id")
            site_id = p.get("site_id")
            week_start = p.get("week_start")
            advance = float(p.get("advance", 0))
            advance_deduction = float(p.get("advance_deduction", 0))
            payment = float(p.get("payment", 0))
            remarks = p.get("remarks", "").strip()
            remaining_advance = advance - advance_deduction

            # Skip rows with missing required fields
            if not (labor_id and site_id and week_start):
                continue

            # Skip sites not assigned to this user (if not admin)
            if role != "admin" and site_id not in site_ids:
                skipped_sites.append(site_id)
                continue

            # Skip rows with no meaningful data
            if advance == 0 and advance_deduction == 0 and payment == 0 and remarks == "":
                continue

            # UPSERT using SQLite syntax
            cur.execute("""
                INSERT INTO payments (client_id, labor_id, site_id, week_start,
                                      advance, advance_deduction, remaining_advance,
                                      payment, remarks)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(client_id, labor_id, site_id, week_start) 
                DO UPDATE SET
                    advance=excluded.advance,
                    advance_deduction=excluded.advance_deduction,
                    remaining_advance=excluded.remaining_advance,
                    payment=excluded.payment,
                    remarks=excluded.remarks
            """, (
                client_id, labor_id, site_id, week_start,
                advance, advance_deduction, remaining_advance,
                payment, remarks
            ))

            saved_count += 1  # ✅ only count rows with actual data

        conn.commit()
        conn.close()

        #msg = f"{saved_count} payment{'s' if saved_count != 1 else ''} saved successfully."
        msg = "Payments saved successfully."
        if skipped_sites:
            msg += f" Skipped rows for unassigned sites: {', '.join(map(str, skipped_sites))}."

        return jsonify({"success": True, "message": msg})

    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify({"success": False, "error": str(e)}), 500




def query_payments(start, end, site_ids=None):
    conn = get_db()
    cur = conn.cursor()

    sql = """
        SELECT p.*, l.name as labor_name, s.name as site_name
        FROM payments p
        JOIN labors l ON p.labor_id = l.id
        JOIN sites s ON p.site_id = s.id
        WHERE p.week_start BETWEEN ? AND ?
    """
    params = [start, end]

    if site_ids is not None and len(site_ids) > 0:
        sql += " AND p.site_id IN ({})".format(",".join(["?"] * len(site_ids)))
        params.extend(site_ids)

    cur.execute(sql, params)
    rows = cur.fetchall()
    conn.close()
    return rows


@app.route("/payments_summary", methods=["GET"])
@login_required
def payments_summary():
    start = request.args.get("start")
    end = request.args.get("end")
    fmt = request.args.get("format", "json").lower()

    if not start or not end:
        return jsonify({"error": "start and end dates are required"}), 400

    user_id = session.get("user_id")
    role = session.get("role")
    site_ids = get_user_site_filter(user_id, role)

    # ✅ Pass site restriction to query
    data = query_payments(start, end, site_ids=site_ids)

    cumulative_advances = {}
    result = []

    for row in data:
        labor_id = row["labor_id"]
        labor_name = row["labor_name"]
        site_id = row["site_id"]
        site_name = row["site_name"]
        week_start = row["week_start"]
        total_hours = float(row["total_hours"] or 0)
        advance = float(row["advance"] or 0)
        advance_deduction = float(row["advance_deduction"] or 0)
        payment = float(row["payment"] or 0)
        remarks = row["remarks"] or ""

        key = (labor_id, site_id)
        prev_remaining = cumulative_advances.get(key, 0)
        remaining_advance = prev_remaining + advance - advance_deduction
        remaining_advance = max(remaining_advance, 0)

        payment_after_deduction = max(payment - advance_deduction, 0)

        cumulative_advances[key] = remaining_advance

        result.append({
            "labor_id": labor_id,
            "labor_name": labor_name,
            "site_id": site_id,
            "site_name": site_name,
            "week_start": week_start,
            "total_hours": total_hours,
            "advance": advance,
            "advance_deduction": advance_deduction,
            "payment": payment,
            "remaining_advance": remaining_advance,
            "payment_after_deduction": payment_after_deduction,
            "remarks": remarks
        })


    if fmt == "json":
        return jsonify(result)

    elif fmt == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            "Labor ID","Labor Name","Site ID","Site Name","Week Start","Total Hours",
            "Advance","Advance Deduction","Payment","Remaining Advance","Payment After Deduction","Remarks"
        ])
        for r in result:
            writer.writerow([
                r["labor_id"], r["labor_name"], r["site_id"], r["site_name"], r["week_start"],
                r["total_hours"], r["advance"], r["advance_deduction"], r["payment"],
                r["remaining_advance"], r["payment_after_deduction"], r["remarks"]
            ])
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment;filename=payments_summary.csv"}
        )

    elif fmt == "pdf":
        buffer = io.BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=A4)
        styles = getSampleStyleSheet()
        elements = []

        elements.append(Paragraph(f"Payments Summary ({start} to {end})", styles['Title']))
        elements.append(Spacer(1, 12))

        table_data = [[
            "Labor ID","Labor Name","Site ID","Site Name","Week Start","Total Hours",
            "Advance","Advance Deduction","Payment","Remaining Advance","Payment After Deduction","Remarks"
        ]]

        for r in result:
            table_data.append([
                r["labor_id"], r["labor_name"], r["site_id"], r["site_name"], r["week_start"],
                r["total_hours"], r["advance"], r["advance_deduction"], r["payment"],
                r["remaining_advance"], r["payment_after_deduction"], r["remarks"]
            ])

        table = Table(table_data, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.grey),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("GRID", (0, 0), (-1, -1), 1, colors.black),
            ("FONTSIZE", (0,0), (-1,-1), 9)
        ]))
        elements.append(table)

        doc.build(elements)
        buffer.seek(0)
        return Response(
            buffer,
            mimetype="application/pdf",
            headers={"Content-Disposition": "attachment;filename=payments_summary.pdf"}
        )

    else:
        return jsonify({"error": "Invalid format"}), 400

def get_labor_report(period="daily"):
    conn = get_db()

    cur = conn.cursor()
    if period == "daily":
        today = datetime.date.today().isoformat()
        cur.execute("""
            SELECT l.name, p.advance, p.payment, p.remarks
            FROM labors l
            LEFT JOIN payments p ON l.id = p.labor_id
            WHERE date(p.id) = ?
        """, (today,))
    else:  # weekly
        today = datetime.date.today()
        week_start = today - datetime.timedelta(days=today.weekday())  # Monday
        week_end = week_start + datetime.timedelta(days=6)
        cur.execute("""
            SELECT l.name, p.advance, p.payment, p.remarks
            FROM labors l
            LEFT JOIN payments p ON l.id = p.labor_id
            WHERE date(p.id) BETWEEN ? AND ?
        """, (week_start.isoformat(), week_end.isoformat()))
    report = cur.fetchall()
    conn.close()
    return report

def get_material_report(period="daily"):
    conn = get_db()

    cur = conn.cursor()
    today = datetime.date.today().isoformat()
    if period == "daily":
        cur.execute("SELECT * FROM site_materials WHERE date(created_at)=?", (today,))
    else:
        today = datetime.date.today()
        week_start = today - datetime.timedelta(days=today.weekday())
        week_end = week_start + datetime.timedelta(days=6)
        cur.execute("SELECT * FROM site_materials WHERE date(created_at) BETWEEN ? AND ?", (week_start.isoformat(), week_end.isoformat()))
    report = cur.fetchall()
    conn.close()
    return report

def get_expenses_report(period="daily"):
    conn = get_db()

    cur = conn.cursor()
    today = datetime.date.today().isoformat()
    if period == "daily":
        cur.execute("SELECT * FROM site_expenses WHERE date(created_at)=?", (today,))
    else:
        today = datetime.date.today()
        week_start = today - datetime.timedelta(days=today.weekday())
        week_end = week_start + datetime.timedelta(days=6)
        cur.execute("SELECT * FROM site_expenses WHERE date(created_at) BETWEEN ? AND ?", (week_start.isoformat(), week_end.isoformat()))
    report = cur.fetchall()
    conn.close()
    return report

# --------------------- REPORTING API --------------------- #

def get_week_start(date_str):
    """Return Monday of the week for a given date string 'YYYY-MM-DD'"""
    d = datetime.strptime(date_str, "%Y-%m-%d")
    monday = d - timedelta(days=d.weekday())
    return monday.strftime("%Y-%m-%d")

# ---------------- PAYMENT CALCULATION ---------------- #
def calculate_and_update_payment(labor_id, week_start, conn, advance_given=0, advance_deduction=0, remarks=""):
    cur = conn.cursor()

    # --- Get daily wage ---
    cur.execute("SELECT wages FROM labors WHERE id=?", (labor_id,))
    row = cur.fetchone()
    if not row:
        return
    daily_wage = float(row["wages"])

    # --- Calculate total payment & hours from attendance ---
    total_payment = 0
    total_hours = 0
    cur.execute("SELECT status, extra_hours FROM attendance WHERE labor_id=? AND week_start=?", (labor_id, week_start))
    for r in cur.fetchall():
        status = r["status"]
        extra = float(r["extra_hours"] or 0)
        if status == "FD":
            total_payment += daily_wage
            total_hours += 8
        elif status == "HD":
            total_payment += daily_wage / 2
            total_hours += 4
        # Extra hours
        total_payment += (daily_wage / 8) * extra
        total_hours += extra

    # --- Get previous remaining advance ---
    cur.execute("""
        SELECT remaining_advance
        FROM payments
        WHERE labor_id=? AND week_start < ?
        ORDER BY week_start DESC LIMIT 1
    """, (labor_id, week_start))
    prev = cur.fetchone()
    prev_remaining = float(prev["remaining_advance"]) if prev else 0

    # --- Calculate current remaining advance & payment after deduction ---
    remaining_advance = prev_remaining + advance_given - advance_deduction
    payment_after_deduction = total_payment - advance_deduction

    # --- Insert or update ---
    cur.execute("""
        INSERT INTO payments (
            labor_id, week_start, total_hours, payment,
            advance, advance_deduction, remaining_advance,
            payment_after_deduction, remarks
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(labor_id, week_start)
        DO UPDATE SET
            total_hours=excluded.total_hours,
            payment=excluded.payment,
            advance=excluded.advance,
            advance_deduction=excluded.advance_deduction,
            remaining_advance=excluded.remaining_advance,
            payment_after_deduction=excluded.payment_after_deduction,
            remarks=excluded.remarks
    """, (
        labor_id, week_start, total_hours, total_payment,
        advance_given, advance_deduction, remaining_advance,
        payment_after_deduction, remarks
    ))
    conn.commit()


# ------------------- Get Report -------------------
from flask import request, jsonify, session
import sqlite3
from database import get_db, get_user_site_filter
from flask import request, jsonify, session
from datetime import datetime
from database import get_db, get_user_site_filter

@app.route("/get_report", methods=["GET"])
def get_report():
    user_id = session.get("user_id")
    role = session.get("role")
    site_ids = get_user_site_filter(user_id, role)

    report_type = request.args.get("type", "attendance")
    start_date = request.args.get("start")
    end_date = request.args.get("end")

    if not start_date or not end_date:
        return jsonify({"columns": [], "rows": [], "message": "Start date and end date are required."})

    weekday_order = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    columns, rows = [], []

    try:
        conn = get_db()
        cur = conn.cursor()

        # ---------------- Attendance ----------------
        if report_type == "attendance":
            query = """
                SELECT a.labor_id, a.site_id, a.week_start, a.day, a.status,
                       COALESCE(a.extra_hours,0) AS extra_hours,
                       l.name AS labor_name, s.name AS site_name
                FROM attendance a
                JOIN labors l ON a.labor_id = l.id
                JOIN sites s ON a.site_id = s.id
                WHERE date(a.day) BETWEEN date(?) AND date(?)
            """
            params = [start_date, end_date]
            if site_ids:
                query += " AND a.site_id IN ({})".format(",".join("?" * len(site_ids)))
                params.extend(site_ids)

            cur.execute(query, params)
            attendance_records = cur.fetchall()

            grouped = {}
            for r in attendance_records:
                key = (r["labor_id"], r["site_id"], r["week_start"])
                if key not in grouped:
                    grouped[key] = {
                        "Labor": r["labor_name"],
                        "Site": r["site_name"],
                        "Week Start": r["week_start"],
                        **{wd: "A" for wd in weekday_order},  # default Absent
                        "Total Extra Hours": 0,
                        "Remarks": ""
                    }

                # Map actual day to weekday column
                try:
                    day_obj = datetime.strptime(r["day"], "%Y-%m-%d")
                    day_key = day_obj.strftime("%a")  # Mon, Tue, etc.
                except Exception:
                    day_key = ""

                if day_key in weekday_order:
                    extra = f" (+{r['extra_hours']}h)" if r["extra_hours"] > 0 else ""
                    grouped[key][day_key] = (r["status"] or "A") + extra

                grouped[key]["Total Extra Hours"] += r["extra_hours"]

            summary = list(grouped.values())
            columns = ["Labor", "Site", "Week Start"] + weekday_order + ["Total Extra Hours", "Remarks"]
            rows = [[s.get(col, "") for col in columns] for s in summary]

        # ---------------- labor Payments ----------------
        elif report_type == "labor":
            query = """
                SELECT l.name AS Labor,
                       s.name AS Site,
                       p.week_start AS WeekStart,
                       COALESCE(SUM(a.extra_hours),0) AS ExtraHours,
                       COALESCE(p.total_hours,0) AS TotalHours,
                       COALESCE(p.advance,0) AS Advance,
                       COALESCE(p.advance_deduction,0) AS AdvanceDeduction,
                       COALESCE(p.remaining_advance,0) AS RemainingAdvance,
                       COALESCE(p.payment,0) AS Payment,
                       COALESCE(p.payment_after_deduction,0) AS PaymentAfterDeduction,
                       COALESCE(p.remarks,'') AS Remarks,
                       COALESCE(p.created_at,'') AS CreatedAt
                FROM payments p
                JOIN labors l ON l.id = p.labor_id
                JOIN sites s ON p.site_id = s.id
                LEFT JOIN attendance a
                       ON a.labor_id = l.id
                      AND a.site_id = p.site_id
                      AND a.week_start = p.week_start
                WHERE date(p.week_start) BETWEEN date(?) AND date(?)
            """
            params = [start_date, end_date]
            if site_ids:
                query += " AND p.site_id IN ({})".format(",".join("?" * len(site_ids)))
                params.extend(site_ids)

            query += """
                GROUP BY l.name, s.name, p.week_start,
                         p.total_hours, p.advance, p.advance_deduction,
                         p.remaining_advance, p.payment, p.payment_after_deduction,
                         p.remarks, p.created_at
                ORDER BY l.name, p.week_start
            """
            cur.execute(query, params)
            recs = cur.fetchall()
            columns = [d[0] for d in cur.description]
            rows = [list(r) for r in recs]

        # ---------------- Materials ----------------
        elif report_type == "material":
            query = """
                SELECT s.name AS Site,
                       m.date AS Date,
                       m.material_name AS Material,
                       m.quantity AS Quantity,
                       m.unit_price AS UnitPrice,
                       m.total AS Total,
                       COALESCE(m.remarks,'') AS Remarks
                FROM site_materials m
                LEFT JOIN sites s ON s.id = m.site_id
                WHERE date(m.date) BETWEEN date(?) AND date(?)
            """
            params = [start_date, end_date]
            if site_ids:
                query += " AND m.site_id IN ({})".format(",".join("?" * len(site_ids)))
                params.extend(site_ids)

            query += " ORDER BY m.date"
            cur.execute(query, params)
            recs = cur.fetchall()
            columns = [d[0] for d in cur.description]
            rows = [list(r) for r in recs]

        # ---------------- Expenses ----------------
        elif report_type == "expenses":
            query = """
                SELECT s.name AS Site,
                       e.date AS Date,
                       e.description AS Description,
                       e.amount AS Amount,
                       COALESCE(e.remarks,'') AS Remarks
                FROM site_expenses e
                LEFT JOIN sites s ON s.id = e.site_id
                WHERE date(e.date) BETWEEN date(?) AND date(?)
            """
            params = [start_date, end_date]
            if site_ids:
                query += " AND e.site_id IN ({})".format(",".join("?" * len(site_ids)))
                params.extend(site_ids)

            query += " ORDER BY e.date"
            cur.execute(query, params)
            recs = cur.fetchall()
            columns = [d[0] for d in cur.description]
            rows = [list(r) for r in recs]

        # ---------------- All Labor (Attendance Grid + Payments) ----------------
        elif report_type == "all_labor":
            query = """
                SELECT l.id AS LaborID,
                       l.name AS Labor,
                       s.name AS Site,
                       a.week_start AS WeekStart,
                       a.day AS Day,
                       a.status AS Status,
                       COALESCE(a.extra_hours,0) AS ExtraHours,
                       COALESCE(p.total_hours,0) AS TotalHours,
                       COALESCE(p.advance,0) AS Advance,
                       COALESCE(p.advance_deduction,0) AS AdvanceDeduction,
                       COALESCE(p.remaining_advance,0) AS RemainingAdvance,
                       COALESCE(p.payment,0) AS Payment,
                       COALESCE(p.payment_after_deduction,0) AS PaymentAfterDeduction,
                       COALESCE(p.remarks,'') AS Remarks,
                       COALESCE(p.created_at,'') AS CreatedAt
                FROM labors l
                JOIN attendance a ON a.labor_id = l.id
                JOIN sites s ON a.site_id = s.id
                LEFT JOIN payments p
                       ON p.labor_id = l.id
                      AND p.site_id = a.site_id
                      AND p.week_start = a.week_start
                WHERE date(a.day) BETWEEN date(?) AND date(?)
            """
            params = [start_date, end_date]
            if site_ids:
                query += " AND a.site_id IN ({})".format(",".join("?" * len(site_ids)))
                params.extend(site_ids)

            cur.execute(query, params)
            recs = cur.fetchall()

            grouped = {}
            for r in recs:
                key = (r["LaborID"], r["Site"], r["WeekStart"])
                if key not in grouped:
                    grouped[key] = {
                        "Labor": r["Labor"],
                        "Site": r["Site"],
                        "Week Start": r["WeekStart"],
                        **{wd: "A" for wd in weekday_order},  # default Absent
                        "Total Extra Hours": 0,
                        "Total Hours": r["TotalHours"],
                        "Advance": r["Advance"],
                        "Advance Deduction": r["AdvanceDeduction"],
                        "Remaining Advance": r["RemainingAdvance"],
                        "Payment": r["Payment"],
                        "Payment After Deduction": r["PaymentAfterDeduction"],
                        "Remarks": r["Remarks"],
                        "Created At": r["CreatedAt"],
                    }

                # Map actual day to weekday column
                try:
                    day_obj = datetime.strptime(r["Day"], "%Y-%m-%d")
                    day_key = day_obj.strftime("%a")
                except Exception:
                    day_key = ""

                if day_key in weekday_order:
                    extra = f" (+{r['ExtraHours']}h)" if r["ExtraHours"] > 0 else ""
                    grouped[key][day_key] = (r["Status"] or "A") + extra

                grouped[key]["Total Extra Hours"] += r["ExtraHours"]

            summary = list(grouped.values())
            columns = ["Labor", "Site", "Week Start"] + weekday_order + [
                "Total Extra Hours", "Total Hours", "Advance", "Advance Deduction",
                "Remaining Advance", "Payment", "Payment After Deduction", "Remarks", "Created At"
            ]
            rows = [[s.get(col, "") for col in columns] for s in summary]

    except Exception as e:
        return jsonify({"columns": [], "rows": [], "message": f"Error: {e}"})
    finally:
        conn.close()

    message = f"Found {len(rows)} records for {report_type}." if rows else f"No {report_type} records found."
    return jsonify({"columns": columns, "rows": rows, "message": message})

import os, csv
from flask import jsonify, request, session, send_file
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from database import get_db, get_user_site_filter

# ---------------- Generate Report Data ----------------

import io
import os
import csv
from io import BytesIO
from flask import request, session, send_file, abort
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from datetime import datetime

# ---------------- Generate Report Data ----------------
def generate_report_data(report_type, start, end, site_ids):
    """
    Generate report data for given type, start/end dates, and site access.
    Always returns dict with keys: 'columns', 'rows'.
    """
    try:
        conn = get_db()
        cur = conn.cursor()
        weekday_order = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]

        # ---------------- Labor Report (Weekly Totals + Payments) ----------------
        if report_type == "labor":
            query = """
                SELECT l.id AS LaborID,
                       l.name AS Labor,
                       s.name AS Site,
                       p.week_start AS WeekStart,
                       COALESCE(SUM(a.extra_hours),0) AS ExtraHours,
                       COALESCE(p.total_hours,0) AS TotalHours,
                       COALESCE(p.advance,0) AS Advance,
                       COALESCE(p.advance_deduction,0) AS AdvanceDeduction,
                       COALESCE(p.remaining_advance,0) AS RemainingAdvance,
                       COALESCE(p.payment,0) AS Payment,
                       COALESCE(p.payment_after_deduction,0) AS PaymentAfterDeduction,
                       COALESCE(p.remarks,'') AS Remarks,
                       COALESCE(p.created_at,'') AS CreatedAt
                FROM labors l
                JOIN sites s ON s.id = l.site_id
                JOIN payments p 
                       ON p.labor_id = l.id 
                      AND p.site_id = s.id
                LEFT JOIN attendance a 
                       ON a.labor_id = l.id 
                      AND a.site_id = s.id 
                      AND a.week_start = p.week_start
                WHERE date(p.week_start) BETWEEN date(?) AND date(?)
            """
            params = [start, end]
            if site_ids:
                query += " AND p.site_id IN ({})".format(",".join("?" * len(site_ids)))
                params.extend(site_ids)

            query += """
                GROUP BY l.id, l.name, s.name, p.week_start,
                         p.total_hours, p.advance, p.advance_deduction, 
                         p.remaining_advance, p.payment, 
                         p.payment_after_deduction, p.remarks, p.created_at
                ORDER BY p.week_start, l.name
            """
            cur.execute(query, params)
            recs = cur.fetchall()
            columns = [d[0] for d in cur.description]
            rows = [list(r) for r in recs]

        # ---------------- All Labor Report (Attendance Grid + Payments) ----------------
        elif report_type == "all_labor":
            query = """
                SELECT l.id AS LaborID,
                       l.name AS Labor,
                       s.name AS Site,
                       a.week_start AS WeekStart,
                       a.day AS Day,
                       a.status AS Status,
                       COALESCE(a.extra_hours,0) AS ExtraHours,
                       COALESCE(p.total_hours,0) AS TotalHours,
                       COALESCE(p.advance,0) AS Advance,
                       COALESCE(p.advance_deduction,0) AS AdvanceDeduction,
                       COALESCE(p.remaining_advance,0) AS RemainingAdvance,
                       COALESCE(p.payment,0) AS Payment,
                       COALESCE(p.payment_after_deduction,0) AS PaymentAfterDeduction,
                       COALESCE(p.remarks,'') AS Remarks,
                       COALESCE(p.created_at,'') AS CreatedAt
                FROM labors l
                JOIN attendance a ON a.labor_id = l.id
                JOIN sites s ON a.site_id = s.id
                LEFT JOIN payments p 
                       ON p.labor_id = l.id 
                      AND p.site_id = a.site_id
                      AND p.week_start = a.week_start
                WHERE date(a.week_start) BETWEEN date(?) AND date(?)
            """
            params = [start, end]
            if site_ids:
                query += " AND a.site_id IN ({})".format(",".join("?" * len(site_ids)))
                params.extend(site_ids)

            cur.execute(query, params)
            recs = cur.fetchall()

            grouped = {}
            for r in recs:
                key = (r["LaborID"], r["Site"], r["WeekStart"])
                if key not in grouped:
                    grouped[key] = {
                        "Labor": r["Labor"],
                        "Site": r["Site"],
                        "Week Start": r["WeekStart"],
                        **{wd: "A" for wd in weekday_order},
                        "Total Extra Hours": 0,
                        "Total Hours": r["TotalHours"],
                        "Advance": r["Advance"],
                        "Advance Deduction": r["AdvanceDeduction"],
                        "Remaining Advance": r["RemainingAdvance"],
                        "Payment": r["Payment"],
                        "Payment After Deduction": r["PaymentAfterDeduction"],
                        "Remarks": r["Remarks"],
                        "Created At": r["CreatedAt"],
                    }

                day_str = r["Day"]
                try:
                    day_obj = datetime.strptime(day_str, "%Y-%m-%d")
                    day_key = day_obj.strftime("%a")
                except Exception:
                    day_key = ""

                if day_key in weekday_order:
                    extra = f" (+{r['ExtraHours']}h)" if r["ExtraHours"] > 0 else ""
                    grouped[key][day_key] = (r["Status"] or "A") + extra

                grouped[key]["Total Extra Hours"] += r["ExtraHours"]

            summary = list(grouped.values())
            columns = ["Labor", "Site", "Week Start"] + weekday_order + [
                "Total Extra Hours", "Total Hours", "Advance", "Advance Deduction",
                "Remaining Advance", "Payment", "Payment After Deduction", "Remarks", "Created At"
            ]
            rows = [[s[col] for col in columns] for s in summary]

        # ---------------- Attendance Report (Pivoted like Labor) ----------------
        elif report_type == "attendance":
            query = """
                SELECT l.id AS LaborID,
                       l.name AS Labor,
                       s.name AS Site,
                       a.week_start AS WeekStart,
                       a.day AS Day,
                       a.status AS Status,
                       COALESCE(a.extra_hours,0) AS ExtraHours
                FROM attendance a
                JOIN labors l ON a.labor_id = l.id
                JOIN sites s ON a.site_id = s.id
                WHERE date(a.week_start) BETWEEN date(?) AND date(?)
            """
            params = [start, end]
            if site_ids:
                query += " AND a.site_id IN ({})".format(",".join("?" * len(site_ids)))
                params.extend(site_ids)

            cur.execute(query, params)
            recs = cur.fetchall()

            grouped = {}
            for r in recs:
                key = (r["LaborID"], r["Site"], r["WeekStart"])
                if key not in grouped:
                    grouped[key] = {
                        "Labor": r["Labor"],
                        "Site": r["Site"],
                        "Week Start": r["WeekStart"],
                        **{wd: "A" for wd in weekday_order},
                        "Total Extra Hours": 0,
                    }

                day_str = r["Day"]
                try:
                    day_obj = datetime.strptime(day_str, "%Y-%m-%d")
                    day_key = day_obj.strftime("%a")
                except Exception:
                    day_key = ""

                if day_key in weekday_order:
                    extra = f" (+{r['ExtraHours']}h)" if r["ExtraHours"] > 0 else ""
                    grouped[key][day_key] = (r["Status"] or "A") + extra

                grouped[key]["Total Extra Hours"] += r["ExtraHours"]

            summary = list(grouped.values())
            columns = ["Labor", "Site", "Week Start"] + weekday_order + ["Total Extra Hours"]
            rows = [[s[col] for col in columns] for s in summary]

        # ---------------- Payments Report ----------------
        elif report_type == "payments":
            query = """
                SELECT l.id AS LaborID,
                       l.name AS Labor,
                       s.name AS Site,
                       p.week_start AS WeekStart,
                       COALESCE(SUM(a.extra_hours),0) AS ExtraHours,
                       COALESCE(p.total_hours,0) AS TotalHours,
                       COALESCE(p.advance,0) AS Advance,
                       COALESCE(p.advance_deduction,0) AS AdvanceDeduction,
                       COALESCE(p.remaining_advance,0) AS RemainingAdvance,
                       COALESCE(p.payment,0) AS Payment,
                       COALESCE(p.payment_after_deduction,0) AS PaymentAfterDeduction,
                       COALESCE(p.remarks,'') AS Remarks,
                       COALESCE(p.created_at,'') AS CreatedAt
                FROM labors l
                JOIN sites s ON s.id = l.site_id
                JOIN payments p 
                       ON p.labor_id = l.id 
                      AND p.site_id = s.id
                LEFT JOIN attendance a 
                       ON a.labor_id = l.id 
                      AND a.site_id = s.id 
                      AND a.week_start = p.week_start
                WHERE date(p.week_start) BETWEEN date(?) AND date(?)
            """
            params = [start, end]
            if site_ids:
                query += " AND p.site_id IN ({})".format(",".join("?" * len(site_ids)))
                params.extend(site_ids)

            query += """
                GROUP BY l.id, l.name, s.name, p.week_start,
                         p.total_hours, p.advance, p.advance_deduction, 
                         p.remaining_advance, p.payment, 
                         p.payment_after_deduction, p.remarks, p.created_at
                ORDER BY p.week_start, l.name
            """
            cur.execute(query, params)
            recs = cur.fetchall()
            columns = [d[0] for d in cur.description]
            rows = [list(r) for r in recs]

        # ---------------- Materials Report ----------------
        elif report_type == "material":
            query = """
                SELECT s.name AS Site,
                       m.date AS Date,
                       m.material_name AS Material,
                       m.quantity AS Quantity,
                       m.unit_price AS UnitPrice,
                       m.total AS Total,
                       COALESCE(m.remarks,'') AS Remarks
                FROM site_materials m
                LEFT JOIN sites s ON s.id = m.site_id
                WHERE date(m.date) BETWEEN date(?) AND date(?)
            """
            params = [start, end]
            if site_ids:
                query += " AND m.site_id IN ({})".format(",".join("?" * len(site_ids)))
                params.extend(site_ids)

            query += " ORDER BY m.date"
            cur.execute(query, params)
            recs = cur.fetchall()
            columns = [d[0] for d in cur.description]
            rows = [list(r) for r in recs]

        # ---------------- Expenses Report ----------------
        elif report_type == "expenses":
            query = """
                SELECT s.name AS Site,
                       e.date AS Date,
                       e.description AS Description,
                       e.amount AS Amount,
                       COALESCE(e.remarks,'') AS Remarks
                FROM site_expenses e
                LEFT JOIN sites s ON s.id = e.site_id
                WHERE date(e.date) BETWEEN date(?) AND date(?)
            """
            params = [start, end]
            if site_ids:
                query += " AND e.site_id IN ({})".format(",".join("?" * len(site_ids)))
                params.extend(site_ids)

            query += " ORDER BY e.date"
            cur.execute(query, params)
            recs = cur.fetchall()
            columns = [d[0] for d in cur.description]
            rows = [list(r) for r in recs]

        # ---------------- Default (No Data) ----------------
        else:
            return {"columns": ["No Data"], "rows": [["No data available"]]}

        conn.close()

        if not rows:
            rows = [["No data available"] + [""] * (len(columns) - 1)]

        return {"columns": columns, "rows": [list(r) for r in rows]}

    except Exception as e:
        print(f"⚠️ generate_report_data error: {e}")
        return {"columns": ["Error"], "rows": [[str(e)]]}



# ---------------- Download Report ----------------

from flask import send_file
import io, os, csv
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
from reportlab.lib.pagesizes import landscape, A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm

@app.route("/download_report")
@login_required
def download_report():
    report_type = request.args.get("type")
    start = request.args.get("start")
    end = request.args.get("end")
    fmt = request.args.get("format", "csv")

    # Get site filter based on user
    site_ids = get_user_site_filter(session["user_id"], session["role"])

    # Generate report data
    data = generate_report_data(report_type, start, end, site_ids)
    if not data or "rows" not in data or len(data["rows"]) == 0:
        return "No data available", 400

    # Ensure reports folder exists
    os.makedirs("reports", exist_ok=True)
    filename = f"{report_type}_{start}_{end}.{fmt}"
    filepath = os.path.join("reports", filename)

    # ----- Fetch client info from DB -----
    import sqlite3
    conn2 = sqlite3.connect("labor.db")
    conn2.row_factory = sqlite3.Row
    cur = conn2.cursor()
    cur.execute("SELECT name, address, phone, email, gst_number, logo FROM business_info WHERE id=?", (1,))
    client = cur.fetchone()
    conn2.close()

    # ---------------- CSV ----------------
    if fmt == "csv":
        with open(filepath, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)

            # Write client/business info at top
            if client:
                writer.writerow(["Client Information"])
                writer.writerow(["Name", client['name']])
                writer.writerow(["Address", client['address']])
                writer.writerow(["Phone", client['phone']])
                writer.writerow(["Email", client['email']])
                writer.writerow(["GST Number", client['gst_number']])
                writer.writerow([])  # blank row

            # Write report title and period
            writer.writerow([f"Report: {report_type}"])
            writer.writerow([f"Period: {start} → {end}"])
            writer.writerow([])

            # Write table header and rows
            writer.writerow(data["columns"])
            writer.writerows(data["rows"])

        return send_file(filepath, as_attachment=True, download_name=filename, mimetype="text/csv")

    # ---------------- PDF ----------------
    elif fmt == "pdf":
        buffer = io.BytesIO()
        page_width, page_height = landscape(A4)
        doc = SimpleDocTemplate(
            buffer, pagesize=landscape(A4),
            leftMargin=1*cm, rightMargin=1*cm,
            topMargin=1*cm, bottomMargin=1*cm
        )
        styles = getSampleStyleSheet()
        elements = []

        # ----- Client Header for PDF -----
        if client:
            header_text = f"""
            <b>Client:</b> {client['name']}<br/>
            <b>Address:</b> {client['address']}<br/>
            <b>Phone:</b> {client['phone']}<br/>
            <b>Email:</b> {client['email']}<br/>
            <b>GST:</b> {client['gst_number']}
            """
            elements.append(Paragraph(header_text, styles["Normal"]))
            elements.append(Spacer(1, 12))

            if client['logo']:
                logo_path = os.path.join("static/uploads", client['logo'])
                if os.path.exists(logo_path):
                    img = Image(logo_path, width=3*cm, height=3*cm)
                    elements.append(img)
                    elements.append(Spacer(1, 12))

        # Report title
        elements.append(Paragraph(f"📊 Report: {report_type}", styles["Heading2"]))
        elements.append(Paragraph(f"Period: {start} → {end}", styles["Normal"]))
        elements.append(Spacer(1, 12))

        # Table data
        table_data = []
        for row in [data["columns"]] + data["rows"]:
            table_data.append([Paragraph(str(cell), styles["Normal"]) for cell in row])

        # Dynamic column widths
        num_cols = len(data["columns"])
        col_max_lengths = [max(len(str(row[i])) for row in [data["columns"]] + data["rows"]) for i in range(num_cols)]
        total_len = sum(col_max_lengths)
        col_widths = [(l / total_len) * (page_width - 2*cm) for l in col_max_lengths]

        # Auto-scale font
        max_table_width = sum(col_widths)
        base_font_size = 10
        font_size = max(6, base_font_size * min(1, (page_width-2*cm)/max_table_width))
        for r, row in enumerate(table_data):
            for c, cell in enumerate(row):
                cell.style.fontSize = font_size

        table = Table(table_data, colWidths=col_widths, repeatRows=1)
        table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), colors.lightblue),
            ('TEXTCOLOR', (0,0), (-1,0), colors.black),
            ('GRID', (0,0), (-1,-1), 0.5, colors.grey),
            ('ALIGN', (0,0), (-1,-1), 'CENTER'),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ]))
        elements.append(table)

        doc.build(elements)
        buffer.seek(0)

        # Save PDF copy
        with open(filepath, "wb") as f:
            f.write(buffer.getvalue())

        buffer.seek(0)
        return send_file(buffer, as_attachment=True, download_name=filename, mimetype="application/pdf")

    return "Invalid format", 400


from datetime import datetime  # at top of your file

@app.route("/save_site_expense", methods=["POST"])
@login_required
def save_site_expense():
    try:
        data = request.get_json()
        site_id = data.get("site_id")
        expense_type = data.get("expense_type", "").strip()
        amount = data.get("amount")
        remarks = data.get("remarks", "").strip()

        # ✅ Get client_id from session (allow 0 for demo)
        client_id = session.get("client_id")
        if client_id is None:   # only reject if not set at all
            return jsonify({"success": False, "message": "❌ Client session not found!"}), 401

        # ✅ Validate site_id
        if not site_id:
            return jsonify({"success": False, "message": "❌ site_id is required"}), 400

        # ✅ Validate expense_type
        if not expense_type:
            return jsonify({"success": False, "message": "❌ Expense type is required"}), 400

        # ✅ Ensure amount is number
        try:
            amount = float(amount)
        except:
            return jsonify({"success": False, "message": "❌ Amount must be a number"}), 400

        # ✅ Date defaults to today
        today = datetime.now().strftime("%Y-%m-%d")

        conn = get_db()
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO site_expenses (client_id, site_id, date, description, amount, remarks)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (client_id, site_id, today, expense_type, amount, remarks))
        conn.commit()
        conn.close()

        return jsonify({"success": True, "message": "✅ Site expense saved successfully!"})

    except Exception as e:
        return jsonify({"success": False, "message": f"❌ Error: {str(e)}"})



@app.route("/save_site_material", methods=["POST"])
@login_required
def save_site_material():
    data = request.get_json()
    if not data:
        return jsonify(success=False, message="No data provided!")

    site_id = data.get("site_id")
    material_name = data.get("material_name", "").strip()
    quantity = float(data.get("quantity", 0))
    unit_price = float(data.get("unit_price", 0))
    remarks = data.get("remarks", "").strip()  # ✅ Added remarks

    if not site_id or not material_name or quantity <= 0 or unit_price <= 0:
        return jsonify(success=False, message="All fields are required and must be valid!")

    client_id = session.get("client_id")
    today = datetime.now().strftime("%Y-%m-%d")
    total = quantity * unit_price

    conn = get_db()
    try:
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO site_materials (client_id, site_id, date, material_name, quantity, unit_price, total, remarks)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (client_id, site_id, today, material_name, quantity, unit_price, total, remarks))  # ✅ Include remarks
        conn.commit()
        return jsonify(success=True, message="Material entry saved successfully!")
    except sqlite3.OperationalError as e:
        conn.rollback()
        return jsonify(success=False, message=f"Database error: {str(e)}")
    finally:
        conn.close()

@app.route('/favicon.ico')
def favicon():
    return send_from_directory(
        os.path.join(app.root_path, 'static'),
        'favicon.ico',
        mimetype='image/vnd.microsoft.icon'
    )

# ------------------------------
# Site Routes
# ------------------------------
@app.route("/get_sites")
@login_required
def get_sites():
    user_id = session.get("user_id")
    role = session.get("role")
    client_id = session.get("client_id")

    site_ids = get_user_site_filter(user_id, role)

    db = get_db()
    cur = db.cursor()

    if site_ids is None:
        # Admin → all active sites
        cur.execute("""
            SELECT id, name, location, start_date, end_date, budget 
            FROM sites 
            WHERE client_id=? AND is_active=1 
            ORDER BY name
        """, (client_id,))
    else:
        if not site_ids:  # no assigned sites
            db.close()
            return jsonify([])
        placeholders = ",".join(["?"] * len(site_ids))
        query = f"""
            SELECT id, name, location, start_date, end_date, budget 
            FROM sites 
            WHERE client_id=? AND is_active=1 
            AND id IN ({placeholders}) 
            ORDER BY name
        """
        cur.execute(query, [client_id] + site_ids)

    sites = cur.fetchall()
    db.close()

    return jsonify([dict(s) for s in sites])


# -----------------------------
# Get plan limits for a client
# -----------------------------
def get_client_plan_limits(db, client_id):
    """
    Returns the max_sites and users_per_site for a client based on their active license.
    """
    cur = db.cursor()
    cur.execute("""
        SELECT p.sites, p.users_per_site
        FROM plans p
        JOIN licenses l ON l.plan_id = p.id
        WHERE l.client_id = ? AND l.status='active'
        ORDER BY l.end_date DESC
        LIMIT 1
    """, (client_id,))
    result = cur.fetchone()
    cur.close()
    if result:
        return result[0], result[1]
    return None, None


# -----------------------------
# Check if admin can add site
# -----------------------------
def can_add_site(db, client_id):
    max_sites, _ = get_client_plan_limits(db, client_id)
    if max_sites is None:
        raise Exception("No active plan found for this client.")

    cur = db.cursor()
    cur.execute("SELECT COUNT(*) FROM sites WHERE client_id=?", (client_id,))
    current_sites = cur.fetchone()[0]
    cur.close()

    if current_sites >= max_sites:
        raise Exception(f"Cannot add more sites. Plan allows maximum {max_sites} sites.Contact Support to upgrade plan")
    return True



# -----------------------------
# Check if admin can add user to a site
# -----------------------------
def can_add_user_to_site(db, client_id, site_id):
    _, users_per_site = get_client_plan_limits(db, client_id)
    if users_per_site is None:
        raise Exception("No active plan found for this client.")

    cur = db.cursor()
    cur.execute("SELECT COUNT(*) FROM users WHERE client_id=? AND site_id=?", (client_id, site_id))
    current_users = cur.fetchone()[0]
    cur.close()

    if current_users >= users_per_site:
        raise Exception(f"Cannot add more users to this site. Plan allows maximum {users_per_site} users per site.Contact Support to upgrade plan")
    return True


# -----------------------------
# Save Site route with limit check
# -----------------------------
@app.route("/save_site", methods=["POST"])
@login_required
def save_site():
    if session.get("role") != "admin":
        return jsonify({"success": False, "message": "Access denied"}), 403

    data = request.json
    db = get_db()
    try:
        # Check site limit
        try:
            can_add_site(db, session["client_id"])
        except Exception as e:
            return jsonify({"success": False, "message": str(e)}), 400

        # Insert new site
        db.execute(
            """
            INSERT INTO sites (client_id, name, location, start_date, end_date, budget) 
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                session["client_id"],
                data.get("name"),
                data.get("location"),
                data.get("start_date"),
                data.get("end_date"),
                data.get("budget", 0),
            ),
        )
        db.commit()
        return jsonify({"success": True, "message": "Site saved successfully"})
    finally:
        db.close()



@app.route("/get_site/<int:id>")
@login_required
def get_site(id):
    user_id = session.get("user_id")
    role = session.get("role")
    client_id = session.get("client_id")
    site_ids = get_user_site_filter(user_id, role)

    db = get_db()
    try:
        if site_ids is None:
            # Admin → any site under this client
            site = db.execute(
                "SELECT * FROM sites WHERE id=? AND client_id=?", (id, client_id)
            ).fetchone()
        else:
            # Engineer → only assigned sites
            if id not in site_ids:
                return jsonify({"success": False, "message": "Access denied"}), 403
            site = db.execute(
                "SELECT * FROM sites WHERE id=? AND client_id=?", (id, client_id)
            ).fetchone()
        if site:
            return jsonify(dict(site))
        return jsonify({"success": False, "message": "Site not found"}), 404
    finally:
        db.close()


@app.route("/update_site/<int:id>", methods=["POST"])
@login_required
def update_site(id):
    if session.get("role") != "admin":
        return jsonify({"success": False, "message": "Access denied"}), 403

    data = request.json
    db = get_db()
    try:
        db.execute(
            """
            UPDATE sites 
            SET name=?, location=?, start_date=?, end_date=?, budget=? 
            WHERE id=? AND client_id=?
            """,
            (
                data.get("name"),
                data.get("location"),
                data.get("start_date"),
                data.get("end_date"),
                data.get("budget", 0),  # ✅ include budget
                id,
                session["client_id"],
            ),
        )
        db.commit()
        return jsonify({"success": True, "message": "Site updated successfully"})
    finally:
        db.close()

@app.route("/delete_site/<int:id>", methods=["POST"])
@login_required
def delete_site(id):
    if session.get("role") != "admin":
        return jsonify({"success": False, "message": "Access denied"}), 403

    db = get_db()
    try:
        db.execute(
            "DELETE FROM sites WHERE id=? AND client_id=?", (id, session["client_id"])
        )
        db.commit()
        return jsonify({"success": True, "message": "Site deleted successfully"})
    finally:
        db.close()



# ------------------
# USERS
# ------------------
# ---------- GET USERS ----------
@app.route("/get_users")
@login_required
def get_users():
    db = get_db()
    users = db.execute(
        "SELECT id, username, email, role FROM users WHERE client_id=? AND is_active=1",
        (session["client_id"],)
    ).fetchall()
    users_list = [dict(u) for u in users]
    db.close()
    return jsonify(users_list)

# ---------- SAVE USER ----------
@app.route('/save_user', methods=['POST'])
@login_required
def save_user():
    data = request.json
    try:
        client_id = session["client_id"]  # Use session client_id
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        role = data.get('role', '').strip()
        password = data.get('password', '').strip()

        if not all([username, email, role, password]):
            return jsonify({'success': False, 'message': 'All fields are required'})

        conn = get_db()
        cursor = conn.cursor()

        # -----------------------------
        # Get active license + plan limits
        # -----------------------------
        cursor.execute("""
            SELECT p.users_per_site
            FROM licenses l
            JOIN plans p ON l.plan_id = p.id
            WHERE l.client_id = ? AND l.status = 'active'
            ORDER BY l.end_date DESC
            LIMIT 1
        """, (client_id,))
        row = cursor.fetchone()

        if row:
            max_users = row[0]

            # Count current users for this client
            cursor.execute("SELECT COUNT(*) FROM users WHERE client_id=?", (client_id,))
            current_users = cursor.fetchone()[0]

            if current_users >= max_users:
                conn.close()
                return jsonify({'success': False, 'message': f'Maximum {max_users} users allowed. Please upgrade your plan.'})

        # -----------------------------
        # Save user if within limit
        # -----------------------------
        hashed_password = generate_password_hash(password)
        cursor.execute(
            "INSERT INTO users (client_id, username, email, role, password) VALUES (?, ?, ?, ?, ?)",
            (client_id, username, email, role, hashed_password)
        )
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'User saved successfully'})

    except sqlite3.IntegrityError as e:
        if 'username' in str(e):
            return jsonify({'success': False, 'message': 'Username already exists'})
        if 'email' in str(e):
            return jsonify({'success': False, 'message': 'Email already exists'})
        return jsonify({'success': False, 'message': str(e)})

    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


# ---------- DELETE USER ----------
@app.route("/delete_user", methods=["POST"])
@login_required
def delete_user():
    data = request.json
    user_id = data.get("id")
    if not user_id:
        return jsonify({"success": False, "message": "User ID required"})
    try:
        db = get_db()
        db.execute(
            "DELETE FROM users WHERE id=? AND client_id=?",
            (user_id, session["client_id"])
        )
        db.commit()
        db.close()
        return jsonify({"success": True, "message": "User deleted successfully"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)})

# ------------------
# LABORS
# ------------------
@app.route("/get_labors", methods=["GET"])
@login_required
def get_labors():
    user_id = session.get("user_id")
    role = session.get("role")
    client_id = session.get("client_id")

    assigned_sites = get_user_site_filter(user_id, role)

    conn = get_conn()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    if role == "admin" or not assigned_sites:
        # Admin sees all labors or engineer with no assigned sites sees none
        cur.execute("SELECT * FROM labors WHERE client_id=? AND is_active=1", (client_id,))
    else:
        # Only labors in sites the engineer is assigned to
        placeholders = ",".join("?" * len(assigned_sites))
        query = f"SELECT * FROM labors WHERE client_id=? AND site_id IN ({placeholders}) AND is_active=1"
        cur.execute(query, (client_id, *assigned_sites))

    labors = [dict(row) for row in cur.fetchall()]
    conn.close()
    return jsonify(labors)


# ------------------------------
# projects Pie Chart
# ------------------------------
@app.route('/get_projects', methods=['GET'])
def get_projects():
    db = get_db()
    cur = db.cursor()

    # Get all sites
    cur.execute("SELECT id, name, budget FROM sites WHERE is_active=1")
    sites = cur.fetchall()

    projects = []
    for site in sites:
        site_id = site['id']

        # Materials
        cur.execute("SELECT SUM(total) as total_materials FROM site_materials WHERE site_id=?", (site_id,))
        materials = cur.fetchone()['total_materials'] or 0

        # Expenses
        cur.execute("SELECT SUM(amount) as total_expenses FROM site_expenses WHERE site_id=?", (site_id,))
        expenses = cur.fetchone()['total_expenses'] or 0

        # Labor payments
        cur.execute("SELECT SUM(payment) as total_labor FROM payments WHERE site_id=?", (site_id,))
        labor = cur.fetchone()['total_labor'] or 0

        projects.append({
            "id": site_id,
            "name": site['name'],
            "budget": site['budget'] or 0,
            "materials": materials,
            "expenses": expenses,
            "labor": labor
        })

    return jsonify(projects)


# ------------------------------
# Save Labor
# ------------------------------
@app.route("/save_labor", methods=["POST"])
def save_labor():
    data = request.get_json()

    # Basic validation
    required_fields = ["name", "address", "phone", "age", "site_id", "role"]
    for field in required_fields:
        if not data.get(field):
            return jsonify({"success": False, "message": f"{field} is required"})

    client_id = session.get("client_id", 1)  # replace with session or default for testing
    db = get_db()
    cur = db.cursor()

    cur.execute("""
        INSERT INTO labors (client_id, site_id, name, address, phone, age, role, upi, bank, aadhaar, emergency, wages)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        client_id,
        data["site_id"],
        data["name"],
        data.get("address"),
        data.get("phone"),
        data.get("age"),
        data.get("role"),
        data.get("upi"),
        data.get("bank"),
        data.get("aadhaar"),
        data.get("emergency"),
        data.get("wages", 0)
    ))

    db.commit()
    return jsonify({"success": True, "message": "Labor saved successfully"})

@app.route("/get_labor/<int:id>")
@login_required
def get_labor(id):
    db = get_db()
    labor = db.execute("SELECT * FROM labors WHERE id=? AND client_id=?", (id, session["client_id"])).fetchone()
    return jsonify(dict(labor))

# ------------------------------
# Update Labor
# ------------------------------
@app.route("/update_labor/<int:labor_id>", methods=["POST"])
@login_required
def update_labor(labor_id):
    data = request.get_json() or {}

    # Require at least a site_id or name if provided for consistency
    if "site_id" not in data and "name" not in data:
        return jsonify({"success": False, "message": "At least site_id or name must be provided"}), 400

    db = get_db()
    cur = db.cursor()

    # --- Engineer auto-assign if labor moved to a new site
    if session.get("role") == "engineer" and "site_id" in data:
        site_ids = get_user_site_filter(session["user_id"], "engineer", conn=db) or []
        if data["site_id"] not in site_ids:
            cur.execute("""
                INSERT OR IGNORE INTO site_assignments (user_id, client_id, site_id)
                VALUES (?, ?, ?)
            """, (session["user_id"], session["client_id"], data["site_id"]))
            db.commit()

    # --- Build update query dynamically (skip missing fields)
    allowed_fields = [
        "site_id", "name", "phone", "role", "wages", "age",
        "address", "aadhaar", "upi", "bank", "emergency"
    ]
    updates = []
    values = []

    for field in allowed_fields:
        if field in data:
            updates.append(f"{field} = ?")
            values.append(data[field])

    if not updates:
        return jsonify({"success": False, "message": "No valid fields provided"}), 400

    values.extend([labor_id, session["client_id"]])
    query = f"""
        UPDATE labors
        SET {', '.join(updates)}
        WHERE id = ? AND client_id = ?
    """

    cur.execute(query, tuple(values))
    db.commit()

    if cur.rowcount == 0:
        return jsonify({"success": False, "message": "Labor not found or not accessible"}), 404

    return jsonify({"success": True, "message": "Labor updated successfully"})

@app.route("/delete_labor", methods=["POST"])
@login_required
def delete_labor():
    data = request.json
    labor_id = data.get("labor_id") or data.get("id")
    if not labor_id:
        return jsonify({"success": False, "message": "Labor ID is required"}), 400

    db = get_db()
    try:
        db.execute(
            "UPDATE labors SET is_active=0 WHERE id=? AND client_id=?",
            (labor_id, session["client_id"])
        )
        db.commit()
        return jsonify({"success": True, "message": "Labor archived successfully"})
    except Exception as e:
        db.rollback()
        return jsonify({"success": False, "message": str(e)}), 500


# ------------------
# BUSINESS INFO
# ------------------
@app.route("/get_business")
@login_required
def get_business():
    db = get_db()
    biz = db.execute("SELECT * FROM business_info WHERE client_id=?", (session["client_id"],)).fetchone()
    return jsonify(dict(biz) if biz else {})

import os
from flask import current_app

# Make sure this folder exists
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), "static/uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

@app.route("/update_business", methods=["POST"])
@login_required
def save_business():
    db = get_db()
    name = request.form.get("name")
    if not name or name.strip() == "":
        return jsonify({"success": False, "message": "Business name is required"})

    address = request.form.get("address")
    phone = request.form.get("phone")
    email = request.form.get("email")
    gst_number = request.form.get("gst_number")
    logo_file = request.files.get("logo")
    logo_name = None

    # Save uploaded logo if provided
    if logo_file:
        logo_name = f"{session['client_id']}_{logo_file.filename}"
        logo_path = os.path.join(UPLOAD_FOLDER, logo_name)
        logo_file.save(logo_path)

    existing = db.execute("SELECT * FROM business_info WHERE client_id=?", (session["client_id"],)).fetchone()
    if existing:
        db.execute("""
            UPDATE business_info 
            SET name=?, address=?, phone=?, email=?, gst_number=?, logo=COALESCE(?, logo)
            WHERE client_id=?
        """, (name, address, phone, email, gst_number, logo_name, session["client_id"]))
        msg = "Business updated successfully"
    else:
        db.execute("""
            INSERT INTO business_info (client_id, name, address, phone, email, gst_number, logo)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (session["client_id"], name, address, phone, email, gst_number, logo_name))
        msg = "Business saved successfully"

    db.commit()
    return jsonify({"success": True, "message": msg})



# ------------------
# SITE ASSIGNMENTS
# ------------------
@app.route("/assign_sites", methods=["POST"])
@login_required
def assign_sites():
    data = request.json
    user_id = data.get("user_id")
    sites = data.get("sites", [])
    client_id = session.get("client_id")

    db = get_db()

    # --------------------------
    # Validate user_id
    # --------------------------
    user_exists = db.execute(
        "SELECT 1 FROM users WHERE id=? AND client_id=?",
        (user_id, client_id)
    ).fetchone()
    if not user_exists:
        return jsonify({"success": False, "message": "Invalid user ID"})

    # --------------------------
    # Validate site IDs
    # --------------------------
    valid_sites = []
    for s in sites:
        site_exists = db.execute(
            "SELECT 1 FROM sites WHERE id=? AND client_id=?",
            (s, client_id)
        ).fetchone()
        if site_exists:
            valid_sites.append(s)

    if not valid_sites:
        return jsonify({"success": False, "message": "No valid sites selected"})

    # --------------------------
    # Get plan limits
    # --------------------------
    max_sites, users_per_site = get_client_plan_limits(db, client_id)
    if max_sites is None or users_per_site is None:
        return jsonify({"success": False, "message": "No active plan found"})

    # --------------------------
    # Check per-site user limit before assigning
    # --------------------------
    for s in valid_sites:
        cur_count = db.execute(
            "SELECT COUNT(*) FROM site_assignments WHERE site_id=? AND client_id=?",
            (s, client_id)
        ).fetchone()[0]

        if cur_count >= users_per_site:
            return jsonify({
                "success": False,
                "message": f"Cannot assign more users to site {s}. Upgrade plan."
            })

    # --------------------------
    # Delete old assignments
    # --------------------------
    db.execute(
        "DELETE FROM site_assignments WHERE user_id=? AND client_id=?",
        (user_id, client_id)
    )

    # --------------------------
    # Insert new assignments
    # --------------------------
    for s in valid_sites:
        db.execute(
            "INSERT OR IGNORE INTO site_assignments (user_id, client_id, site_id) VALUES (?,?,?)",
            (user_id, client_id, s)
        )

    db.commit()
    return jsonify({"success": True, "message": "Sites assigned successfully"})


# --------------------- RUN --------------------- #

def run_flask():
    init_db()
    conn = get_db()

    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            labor_id INTEGER NOT NULL,
            weekday INTEGER NOT NULL,
            status TEXT,
            UNIQUE(labor_id, weekday),
            FOREIGN KEY(labor_id) REFERENCES labors(id)
        )
    """)
    conn.commit()
    conn.close()
    app.run(debug=False, port=5000, use_reloader=False)

# ------------------------------
# Flask run in background thread
# ------------------------------
from sync_manager import continuous_sync
import threading
import os, webview
import time

# Global sync control
stop_event = None
sync_thread = None

def start_sync(client_id):
    """Start background sync thread for a specific client (only once)."""
    global stop_event, sync_thread
    if sync_thread and sync_thread.is_alive():
        return  # already running

    stop_event = threading.Event()
    sync_thread = threading.Thread(
        target=continuous_sync,
        args=(stop_event, client_id),  # pass stop_event and client_id
        daemon=True
    )
    sync_thread.start()
    print(f"🔄 Sync started in background for client {client_id}")



def run_flask():
    # Use get_conn() here, never get_db()
    conn = get_conn()
    conn.close()

    # Start Flask server
    app.run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)


# ------------------------------
# Main entrypoint
# ------------------------------
if __name__ == "__main__":
    # Init DB once at startup
    init_db()

    # Start Flask in background thread
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()

    # Create a persistent folder for Edge/CEF storage (optional)
    webview_data_dir = os.path.join(os.getcwd(), "webview_data")
    os.makedirs(webview_data_dir, exist_ok=True)

    # Launch desktop window
    webview.create_window(
        "Labor Management",
        "http://127.0.0.1:5000/"
    )
    try:
        webview.start()
    except KeyboardInterrupt:
        print("👋 Application closed by user")
        stop_sync()   # ensure sync stops when app closes