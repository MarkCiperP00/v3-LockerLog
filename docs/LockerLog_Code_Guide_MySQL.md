# LockerLog – Code Guide (Flask + MySQL + Tailwind)

> **Paalala:** Hindi ito na-test sa aktuwal na MySQL server (wala sa environment ko). Patakbuhin muna sa MySQL **8.0.16 o mas bago** (kailangan para sa CHECK constraints). Ang mga file names ay mungkahi lang; iangkop sa project ninyo.

## 1. Setup

```bash
python -m venv venv
venv\Scripts\activate          # Windows  (Linux/Mac: source venv/bin/activate)
pip install flask mysql-connector-python
mysql -u root -p < schema.sql   # gagawa ng database na "lockerlog"
python seed.py                  # lockers, semesters, sample users
flask --app app run --debug
```

```
lockerlog/
├── app.py
├── config.py
├── db.py
├── models.py              # User, Borrower, Student, ProfessorStaff, Maintenance, Administrator
├── services/
│   ├── fees.py            # get_rate_per_day, compute_assignment
│   └── rentals.py         # submit, approve, reject, cancel, release, expire
├── templates/
│   ├── base.html  login.html  lockers.html  request_form.html  my_locker.html
│   ├── maintenance.html
│   └── admin/ dashboard.html  requests.html  lockers.html  settings.html  log.html
├── schema.sql
└── seed.py
```

## 2. config.py at db.py (Yoo)

```python
# config.py
import os
SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-in-production")
DB = dict(host="localhost", user="root", password=os.environ.get("DB_PASSWORD", ""),
          database="lockerlog")
```

```python
# db.py
import mysql.connector
from flask import g
import config

def get_db():
    if "db" not in g:
        g.db = mysql.connector.connect(**config.DB)
    return g.db

def close_db(e=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()

def query(sql, params=(), one=False):
    cur = get_db().cursor(dictionary=True)
    cur.execute(sql, params)
    rows = cur.fetchall()
    cur.close()
    return (rows[0] if rows else None) if one else rows

def log_action(school_id, action, locker_id=None, rule_blocked=None):
    """Write to activity_log (separate commit so blocked attempts are still saved)."""
    db = get_db()
    cur = db.cursor()
    cur.execute("INSERT INTO activity_log (school_id, action, locker_id, rule_blocked) "
                "VALUES (%s, %s, %s, %s)", (school_id, action, locker_id, rule_blocked))
    db.commit()
    cur.close()
```

**Mga pagbabago mula SQLite:** `%s` na ang placeholder (hindi `?`), `cursor(dictionary=True)` para dict ang rows, at `setting_key` / `setting_value` ang columns sa settings.

## 3. services/fees.py (Abuan)

```python
from decimal import Decimal
from db import query

def get_rate_per_day():
    row = query("SELECT setting_value FROM settings WHERE setting_key=%s",
                ("rate_per_day",), one=True)
    return Decimal(row["setting_value"])

def compute_assignment(semester, approval_date, rate_per_day):
    """Return (date_start, date_end, days, total_fee). Prorated from approval date."""
    sem_start, sem_end = semester["date_start"], semester["date_end"]  # date objects
    start = max(approval_date, sem_start)
    if start >= sem_end:
        raise ValueError("Semester has already ended")
    days = (sem_end - start).days + 1
    return start, sem_end, days, (rate_per_day * days).quantize(Decimal("0.01"))
```

## 4. services/rentals.py (Abuan)

```python
import uuid
from datetime import date
import mysql.connector
from db import get_db, log_action
from services.fees import get_rate_per_day, compute_assignment

class RuleError(Exception):
    """Raised when a business rule blocks an action."""

def _id(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:8]}"

def submit_request(user, locker_id, semester_id):
    db = get_db()
    cur = db.cursor(dictionary=True)
    try:
        db.start_transaction()
        cur.execute("SELECT status FROM lockers WHERE locker_id=%s FOR UPDATE", (locker_id,))
        locker = cur.fetchone()
        if not locker or locker["status"] != "Available":
            raise RuleError("Only an Available locker can be requested")
        cur.execute("SELECT 1 FROM rental_requests WHERE school_id=%s AND status='Pending'",
                    (user.school_id,))
        if cur.fetchone():
            raise RuleError("You already have a pending request")
        cur.execute("SELECT 1 FROM assignments WHERE school_id=%s "
                    "AND status IN ('Active','Expired')", (user.school_id,))
        if cur.fetchone():
            raise RuleError("You already have an active locker")
        cur.execute("SELECT date_end FROM semesters WHERE semester_id=%s", (semester_id,))
        sem = cur.fetchone()
        if not sem or sem["date_end"] <= date.today():
            raise RuleError("That semester has already ended")
        cur.execute("INSERT INTO rental_requests (request_id, school_id, locker_id, semester_id) "
                    "VALUES (%s,%s,%s,%s)", (_id("REQ"), user.school_id, locker_id, semester_id))
        cur.execute("UPDATE lockers SET status='Reserved' WHERE locker_id=%s", (locker_id,))
        db.commit()
        log_action(user.school_id, "request_submitted", locker_id)
    except RuleError as e:
        db.rollback()
        log_action(user.school_id, "request_blocked", locker_id, str(e))
        raise
    except mysql.connector.IntegrityError:        # unique index caught a duplicate
        db.rollback()
        log_action(user.school_id, "request_blocked", locker_id, "Duplicate request (database)")
        raise RuleError("Duplicate request blocked")
    finally:
        cur.close()

def approve_request(admin, request_id):
    """One transaction: assignment + locker + request. No dates are typed in."""
    db = get_db()
    cur = db.cursor(dictionary=True)
    try:
        db.start_transaction()
        cur.execute("SELECT * FROM rental_requests WHERE request_id=%s AND status='Pending' "
                    "FOR UPDATE", (request_id,))
        req = cur.fetchone()
        if not req:
            raise RuleError("Request is no longer pending")
        cur.execute("SELECT * FROM semesters WHERE semester_id=%s", (req["semester_id"],))
        sem = cur.fetchone()
        rate = get_rate_per_day()
        start, end, days, fee = compute_assignment(sem, date.today(), rate)   # ValueError if ended
        cur.execute("INSERT INTO assignments (assignment_id, request_id, school_id, locker_id, "
                    "semester_id, date_start, date_end, rate_per_day, total_fee, assigned_by) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (_id("ASG"), request_id, req["school_id"], req["locker_id"],
                     req["semester_id"], start, end, rate, fee, admin.school_id))
        cur.execute("UPDATE lockers SET status='Assigned' WHERE locker_id=%s", (req["locker_id"],))
        cur.execute("UPDATE rental_requests SET status='Approved' WHERE request_id=%s", (request_id,))
        db.commit()
        log_action(admin.school_id, "request_approved", req["locker_id"])
    except (RuleError, ValueError) as e:
        db.rollback()
        log_action(admin.school_id, "approve_blocked", None, str(e))
        raise RuleError(str(e))
    except Exception:
        db.rollback()          # kahit anong error: walang kalahating na-save
        raise
    finally:
        cur.close()

def _finish_request(user, request_id, new_status, allowed_owner=None):
    db = get_db()
    cur = db.cursor(dictionary=True)
    try:
        db.start_transaction()
        cur.execute("SELECT * FROM rental_requests WHERE request_id=%s AND status='Pending' "
                    "FOR UPDATE", (request_id,))
        req = cur.fetchone()
        if not req or (allowed_owner and req["school_id"] != allowed_owner):
            raise RuleError("Request not found or not yours")
        cur.execute("UPDATE rental_requests SET status=%s WHERE request_id=%s", (new_status, request_id))
        cur.execute("UPDATE lockers SET status='Available' WHERE locker_id=%s", (req["locker_id"],))
        db.commit()
        log_action(user.school_id, f"request_{new_status.lower()}", req["locker_id"])
    except RuleError as e:
        db.rollback()
        log_action(user.school_id, f"{new_status.lower()}_blocked", None, str(e))
        raise
    finally:
        cur.close()

def reject_request(admin, request_id):  _finish_request(admin, request_id, "Rejected")
def cancel_request(user, request_id):   _finish_request(user, request_id, "Cancelled", user.school_id)

def release_assignment(admin, assignment_id):
    db = get_db()
    cur = db.cursor(dictionary=True)
    try:
        db.start_transaction()
        cur.execute("SELECT * FROM assignments WHERE assignment_id=%s "
                    "AND status IN ('Active','Expired') FOR UPDATE", (assignment_id,))
        a = cur.fetchone()
        if not a:
            raise RuleError("Assignment not found or already released")
        cur.execute("UPDATE assignments SET status='Released' WHERE assignment_id=%s", (assignment_id,))
        cur.execute("UPDATE lockers SET status='Available' WHERE locker_id=%s", (a["locker_id"],))
        db.commit()
        log_action(admin.school_id, "locker_released", a["locker_id"])
    except RuleError:
        db.rollback()
        raise
    finally:
        cur.close()

def expire_assignments():
    """Run on every admin/maintenance page load (or on a schedule)."""
    db = get_db()
    cur = db.cursor()
    cur.execute("UPDATE lockers l JOIN assignments a ON a.locker_id=l.locker_id "
                "SET l.status='Expired' WHERE a.status='Active' AND a.date_end < CURDATE()")
    cur.execute("UPDATE assignments SET status='Expired' WHERE status='Active' AND date_end < CURDATE()")
    db.commit()
    cur.close()

def set_maintenance_status(user, locker_id, new_status):
    if new_status not in ("Available", "Under Maintenance"):
        raise RuleError("Invalid status")
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT status FROM lockers WHERE locker_id=%s FOR UPDATE", (locker_id,))
    row = cur.fetchone()
    if not row or row["status"] not in ("Available", "Under Maintenance"):
        db.rollback(); cur.close()
        log_action(user.school_id, "maintenance_blocked", locker_id, "Locker is Reserved/Assigned/Expired")
        raise RuleError("Reserved or Assigned lockers cannot be changed")
    cur.execute("UPDATE lockers SET status=%s WHERE locker_id=%s", (new_status, locker_id))
    db.commit(); cur.close()
    log_action(user.school_id, f"maintenance_{new_status.replace(' ', '_').lower()}", locker_id)
```

> Ang **Expired** na locker ay nililinis ng Maintenance (inspect/clear), tapos ang **Administrator** ang nagre-release (`release_assignment`) at nagiging Available ulit, ayon sa activity diagram.

## 5. models.py (Abuan)

Kopyahin ang `User`, `Borrower`, `Student`, `ProfessorStaff`, `Maintenance`, `Administrator`, `USER_CLASSES`, at `create_user()` mula sa Section 9d ng proposal. Dagdag sa itaas:

```python
from werkzeug.security import check_password_hash
```

## 6. app.py (Abuan – routes)

```python
from functools import wraps
from flask import Flask, render_template, request, redirect, session, flash, abort, jsonify, g
import config
from db import query, close_db, get_db
from models import create_user
from services import rentals
from services.rentals import RuleError
from services.fees import get_rate_per_day, compute_assignment
from datetime import date

app = Flask(__name__)
app.secret_key = config.SECRET_KEY
app.teardown_appcontext(close_db)

def current_user():
    if "school_id" not in session:
        return None
    row = query("SELECT * FROM users WHERE school_id=%s", (session["school_id"],), one=True)
    return create_user(row) if row else None

def needs(action):
    """Decorator: login + permission check. Polymorphism: user.can(action)."""
    def deco(f):
        @wraps(f)
        def wrapper(*a, **kw):
            user = current_user()
            if not user:
                return redirect("/login")
            if not user.can(action):
                rentals.log_action(user.school_id, "access_denied", None, f"Missing permission: {action}")
                abort(403)
            g.user = user
            return f(*a, **kw)
        return wrapper
    return deco

@app.route("/", methods=["GET"])
def index():
    user = current_user()
    return redirect(user.dashboard_route() if user else "/login")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        row = query("SELECT * FROM users WHERE school_id=%s", (request.form["school_id"],), one=True)
        user = create_user(row) if row else None
        if user and user.verify_password(request.form["password"]):
            session["school_id"] = user.school_id
            return redirect(user.dashboard_route())
        flash("Incorrect ID number or password")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")

# ---------- Borrower ----------
@app.route("/lockers")
@needs("view_availability")
def lockers():
    where, params = ["1=1"], []
    for col in ("building", "floor", "status"):
        if request.args.get(col):
            where.append(f"{col}=%s"); params.append(request.args[col])
    rows = query(f"SELECT * FROM lockers WHERE {' AND '.join(where)} ORDER BY building, floor, locker_id", params)
    return render_template("lockers.html", lockers=rows, user=g.user)

@app.route("/request/<locker_id>", methods=["GET", "POST"])
@needs("request_locker")
def request_locker(locker_id):
    sems = query("SELECT * FROM semesters WHERE date_end > CURDATE() ORDER BY date_start")
    if request.method == "POST":
        try:
            rentals.submit_request(g.user, locker_id, request.form["semester_id"])
            flash("Request submitted. Wait for the administrator's decision.")
            return redirect("/my-locker")
        except RuleError as e:
            flash(str(e))
    return render_template("request_form.html", locker_id=locker_id, semesters=sems,
                           rate=get_rate_per_day())

@app.route("/api/fee")                      # fee preview (prorated from today)
@needs("request_locker")
def fee_preview():
    sem = query("SELECT * FROM semesters WHERE semester_id=%s", (request.args.get("semester_id"),), one=True)
    try:
        start, end, days, fee = compute_assignment(sem, date.today(), get_rate_per_day())
        return jsonify(start=str(start), end=str(end), days=days, fee=str(fee))
    except (ValueError, TypeError):
        return jsonify(error="Semester has already ended"), 400

@app.route("/my-locker")
@needs("view_own_locker")
def my_locker():
    uid = g.user.school_id
    asg = query("SELECT a.*, s.school_year, s.term FROM assignments a "
                "JOIN semesters s USING (semester_id) "
                "WHERE a.school_id=%s AND a.status IN ('Active','Expired')", (uid,), one=True)
    pending = query("SELECT * FROM rental_requests WHERE school_id=%s AND status='Pending'", (uid,), one=True)
    return render_template("my_locker.html", asg=asg, pending=pending, user=g.user)

@app.route("/cancel/<request_id>", methods=["POST"])
@needs("cancel_request")
def cancel(request_id):
    try: rentals.cancel_request(g.user, request_id); flash("Request cancelled.")
    except RuleError as e: flash(str(e))
    return redirect("/my-locker")

# ---------- Administrator ----------
@app.route("/admin")
@needs("view_usage")
def admin_dashboard():
    rentals.expire_assignments()
    usage = query("SELECT status, COUNT(*) AS n FROM lockers GROUP BY status")
    pending = query("SELECT r.*, DATEDIFF(CURDATE(), r.date_submitted) AS days_waiting "
                    "FROM rental_requests r WHERE status='Pending' ORDER BY date_submitted")
    log = query("SELECT * FROM activity_log ORDER BY logged_at DESC LIMIT 20")
    return render_template("admin/dashboard.html", usage=usage, pending=pending, log=log)

@app.route("/admin/requests")
@needs("review_requests")
def admin_requests():
    rows = query("SELECT r.*, u.name, s.school_year, s.term, DATEDIFF(CURDATE(), r.date_submitted) AS days_waiting "
                 "FROM rental_requests r JOIN users u USING (school_id) JOIN semesters s USING (semester_id) "
                 "WHERE r.status='Pending' ORDER BY r.date_submitted")
    return render_template("admin/requests.html", requests=rows)    # flag days_waiting > 3

@app.route("/admin/requests/<request_id>/<decision>", methods=["POST"])
@needs("review_requests")
def admin_decide(request_id, decision):
    try:
        if decision == "approve": rentals.approve_request(g.user, request_id)
        elif decision == "reject": rentals.reject_request(g.user, request_id)
        else: abort(404)
        flash(f"Request {decision}d.")
    except RuleError as e:
        flash(str(e))
    return redirect("/admin/requests")

@app.route("/admin/release/<assignment_id>", methods=["POST"])
@needs("release_locker")
def admin_release(assignment_id):
    try: rentals.release_assignment(g.user, assignment_id); flash("Locker released.")
    except RuleError as e: flash(str(e))
    return redirect("/admin/lockers")

@app.route("/admin/settings", methods=["GET", "POST"])
@needs("manage_lockers")
def admin_settings():
    db = get_db()
    if request.method == "POST":
        cur = db.cursor()
        if request.form.get("rate_per_day"):
            cur.execute("UPDATE settings SET setting_value=%s WHERE setting_key='rate_per_day'",
                        (request.form["rate_per_day"],))
        if request.form.get("semester_id"):          # add or update a semester
            cur.execute("REPLACE INTO semesters (semester_id, school_year, term, date_start, date_end) "
                        "VALUES (%s,%s,%s,%s,%s)",
                        (request.form["semester_id"], request.form["school_year"], request.form["term"],
                         request.form["date_start"], request.form["date_end"]))
        db.commit(); cur.close()
        rentals.log_action(g.user.school_id, "settings_changed")
        flash("Saved.")
    return render_template("admin/settings.html", rate=get_rate_per_day(),
                           semesters=query("SELECT * FROM semesters ORDER BY date_start"))

# ---------- Maintenance ----------
@app.route("/maintenance", methods=["GET", "POST"])
@needs("set_maintenance_status")
def maintenance():
    rentals.expire_assignments()
    if request.method == "POST":
        try: rentals.set_maintenance_status(g.user, request.form["locker_id"], request.form["status"]); flash("Updated.")
        except RuleError as e: flash(str(e))
    where, params = ["1=1"], []
    for col in ("building", "floor", "status"):
        if request.args.get(col):
            where.append(f"{col}=%s"); params.append(request.args[col])
    rows = query(f"SELECT * FROM lockers WHERE {' AND '.join(where)} ORDER BY building, floor, locker_id", params)
    return render_template("maintenance.html", lockers=rows)
```

Mga routes pa na gagayahin ang pattern sa itaas (Villar/Abuan): `/admin/lockers` (list + add/edit/delete, may Release button sa Expired/Active), `/admin/log` (full activity log).

## 7. Templates na may Tailwind (Caliao at Villar)

Para sa development, ang **Tailwind Play CDN** ang pinakamadali (walang build step):

```html
<!-- templates/base.html -->
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}LockerLog{% endblock %}</title>
  <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-slate-50 text-slate-800 min-h-screen">
  <nav class="bg-blue-900 text-white px-6 py-3 flex items-center justify-between">
    <a href="/" class="font-bold text-lg">LockerLog</a>
    {% if session.school_id %}
      <div class="flex gap-4 text-sm items-center">
        <span>{{ session.school_id }}</span>
        <a class="underline" href="/logout">Log out</a>
      </div>
    {% endif %}
  </nav>
  <main class="max-w-5xl mx-auto p-6">
    {% with msgs = get_flashed_messages() %}
      {% for m in msgs %}
        <div class="mb-4 rounded border border-amber-300 bg-amber-50 px-4 py-2 text-sm">{{ m }}</div>
      {% endfor %}
    {% endwith %}
    {% block content %}{% endblock %}
  </main>
</body>
</html>
```

> Para sa final na submission/deploy, mas maganda ang Tailwind CLI (`npm install -D tailwindcss` → `npx tailwindcss -i input.css -o static/app.css --minify`) at i-link ang `static/app.css` sa halip na CDN. Ang CDN ay para lang sa development.

```html
<!-- templates/login.html (Caliao) -->
{% extends "base.html" %}
{% block content %}
<form method="post" class="max-w-sm mx-auto mt-16 bg-white p-6 rounded-lg shadow space-y-4">
  <h1 class="text-xl font-bold text-center">Log in</h1>
  <input name="school_id" placeholder="School ID number" required
         class="w-full border rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500">
  <input type="password" name="password" placeholder="Password" required
         class="w-full border rounded px-3 py-2 focus:outline-none focus:ring-2 focus:ring-blue-500">
  <button class="w-full bg-blue-900 text-white py-2 rounded hover:bg-blue-800">Log in</button>
</form>
{% endblock %}
```

```html
<!-- templates/lockers.html (Caliao): filter + status badges -->
{% extends "base.html" %}
{% block content %}
<form method="get" class="flex flex-wrap gap-3 mb-4">
  <select name="building" class="border rounded px-2 py-1">
    <option value="">All buildings</option>
    {% for b in ["COECSA","Sotero","JPL"] %}<option {{ "selected" if request.args.building==b }}>{{ b }}</option>{% endfor %}
  </select>
  <input name="floor" type="number" placeholder="Floor" value="{{ request.args.floor or '' }}" class="border rounded px-2 py-1 w-24">
  <select name="status" class="border rounded px-2 py-1">
    <option value="">Any status</option>
    {% for s in ["Available","Reserved","Assigned","Expired","Under Maintenance"] %}
      <option {{ "selected" if request.args.status==s }}>{{ s }}</option>{% endfor %}
  </select>
  <button class="bg-blue-900 text-white px-4 rounded">Filter</button>
</form>
<div class="grid grid-cols-2 sm:grid-cols-4 gap-3">
  {% for l in lockers %}
  <div class="bg-white rounded shadow p-3 text-sm">
    <div class="font-semibold">{{ l.locker_id }}</div>
    <div class="text-slate-500">{{ l.building }} · Floor {{ l.floor }}</div>
    {% set colors = {"Available":"bg-green-100 text-green-800","Reserved":"bg-yellow-100 text-yellow-800",
                     "Assigned":"bg-blue-100 text-blue-800","Expired":"bg-red-100 text-red-800",
                     "Under Maintenance":"bg-slate-200 text-slate-700"} %}
    <span class="inline-block mt-1 px-2 py-0.5 rounded text-xs {{ colors[l.status] }}">{{ l.status }}</span>
    {% if l.status == "Available" and user.can("request_locker") %}
      <a href="/request/{{ l.locker_id }}" class="block mt-2 text-blue-700 underline">Request</a>
    {% endif %}
  </div>
  {% endfor %}
</div>
{% endblock %}
```

```html
<!-- templates/request_form.html (Caliao): semester dropdown + fee preview -->
{% extends "base.html" %}
{% block content %}
<form method="post" class="max-w-md bg-white p-6 rounded-lg shadow space-y-4">
  <h1 class="text-xl font-bold">Request locker {{ locker_id }}</h1>
  <select id="sem" name="semester_id" required class="w-full border rounded px-3 py-2">
    <option value="">Choose semester</option>
    {% for s in semesters %}
      <option value="{{ s.semester_id }}">{{ s.school_year }} – Semester {{ s.term }} ({{ s.date_start }} to {{ s.date_end }})</option>
    {% endfor %}
  </select>
  <div id="preview" class="text-sm text-slate-600">Rate: ₱{{ rate }} per day</div>
  <button class="w-full bg-blue-900 text-white py-2 rounded">Submit request</button>
  <p class="text-xs text-slate-500">Payment is made at the cashier. The system does not detect payment.</p>
</form>
<script>
document.getElementById("sem").addEventListener("change", async e => {
  const box = document.getElementById("preview");
  if (!e.target.value) { box.textContent = "Rate: ₱{{ rate }} per day"; return; }
  const r = await fetch("/api/fee?semester_id=" + encodeURIComponent(e.target.value));
  const d = await r.json();
  box.textContent = d.error ? d.error
    : `${d.days} days (${d.start} to ${d.end}) × ₱{{ rate }} = ₱${d.fee}`;
});
</script>
{% endblock %}
```

**Natitirang templates (sundin ang parehong Tailwind pattern):**

| Template | Gumagawa | Laman |
|---|---|---|
| `my_locker.html` | Caliao | Locker, location, start date, expiry date, **total fee**, paalalang magbayad sa cashier; Cancel button kapag may pending request |
| `maintenance.html` | Caliao | Filter (building/floor/status); form na may Available / Under Maintenance button para sa bawat locker |
| `admin/dashboard.html` | Villar | Usage counts, pending requests (naka-highlight kapag `days_waiting > 3`), huling 20 log entries |
| `admin/requests.html` | Villar | Approve at Reject buttons lang. **Walang date inputs** |
| `admin/lockers.html` | Villar | Add/edit/remove lockers, Release button sa Active/Expired |
| `admin/settings.html` | Villar | Daily rate input at semester form (id, school year, term, start, end) |

Halimbawa ng admin requests row (walang date input):

```html
{% for r in requests %}
<tr class="border-t {{ 'bg-red-50' if r.days_waiting > 3 }}">
  <td class="p-2">{{ r.name }} ({{ r.school_id }})</td>
  <td class="p-2">{{ r.locker_id }}</td>
  <td class="p-2">{{ r.school_year }} – Sem {{ r.term }}</td>
  <td class="p-2">{{ r.days_waiting }} day(s){{ ' – FLAGGED' if r.days_waiting > 3 }}</td>
  <td class="p-2 flex gap-2">
    <form method="post" action="/admin/requests/{{ r.request_id }}/approve"><button class="bg-green-700 text-white px-3 py-1 rounded">Approve</button></form>
    <form method="post" action="/admin/requests/{{ r.request_id }}/reject"><button class="bg-red-700 text-white px-3 py-1 rounded">Reject</button></form>
  </td>
</tr>
{% endfor %}
```

## 8. seed.py (Yoo)

```python
import mysql.connector
from datetime import date
from werkzeug.security import generate_password_hash
import config

db = mysql.connector.connect(**config.DB)
cur = db.cursor()

# Lockers: COECSA floors 2,3,5,6,7,8 x15 | Sotero 2,3,4 x20 | JPL 2,3,4 x20  (= 210)
plan = {"COECSA": ([2, 3, 5, 6, 7, 8], 15), "Sotero": ([2, 3, 4], 20), "JPL": ([2, 3, 4], 20)}
for b, (floors, n) in plan.items():
    for f in floors:
        for i in range(1, n + 1):
            cur.execute("INSERT IGNORE INTO lockers (locker_id, building, floor) VALUES (%s,%s,%s)",
                        (f"{b[:3].upper()}-{f}{i:02d}", b, f))

# DUMMY semester dates - palitan ng totoong academic calendar
cur.executemany("REPLACE INTO semesters VALUES (%s,%s,%s,%s,%s)", [
    ("2026-2027-1", "2026-2027", 1, date(2026, 8, 17), date(2026, 12, 19)),
    ("2026-2027-2", "2026-2027", 2, date(2027, 1, 11), date(2027, 5, 29)),
])

# Sample accounts - palitan ang passwords (dapat may capital letter at special character)
users = [("2025-2-00001", "Sample Student", "student@lpu.test", "Student#123", "Student"),
         ("EMP-0001", "Sample Professor", "prof@lpu.test", "Prof#12345", "Professor/Staff"),
         ("MNT-0001", "Sample Maintenance", "mnt@lpu.test", "Maint#12345", "Maintenance"),
         ("ADM-0001", "Sample Admin", "admin@lpu.test", "Admin#12345", "Administrator")]
for sid, name, email, pw, role in users:
    cur.execute("INSERT IGNORE INTO users VALUES (%s,%s,%s,%s,%s)",
                (sid, name, email, generate_password_hash(pw), role))
db.commit()
print("Seeded.")
```

Para sa password rule (may capital letters at special characters), magdagdag ng check sa registration/seed:

```python
import re
def valid_password(p):
    return len(p) >= 8 and re.search(r"[A-Z]", p) and re.search(r"[^A-Za-z0-9]", p)
```

## 9. Sino ang gagawa ng ano

| Miyembro | Files | Gagawin |
|---|---|---|
| **Yoo** | `schema.sql`, `config.py`, `db.py`, `seed.py` | I-run ang schema sa MySQL 8.0.16+, i-seed ang lockers at semesters (totoong dates), subukan ang unique indexes (tingnan ang test checklist) |
| **Abuan** | `models.py`, `services/*`, `app.py` | Routes, transaction sa approve, expiry check, fee computation, activity log |
| **Caliao** | `base.html`, `login.html`, `lockers.html`, `request_form.html`, `my_locker.html`, `maintenance.html` | Tailwind pages ng Student/Staff at Maintenance |
| **Villar** | `admin/*.html` | Tailwind pages ng Administrator, kasama ang settings page |

## 10. Test checklist (Yoo)

1. **Login:** maling password → "Incorrect ID number or password". Tamang login → tamang dashboard bawat role.
2. **Request:** Available locker + semester → locker nagiging **Reserved**, request **Pending**.
3. **Double-booking:** ikalawang user na magre-request ng parehong locker → "Only an Available locker can be requested" + may row sa activity log.
4. **Duplicate:** parehong user, pangalawang request (o i-double-click ang Submit) → blocked.
5. **Race test:** buksan ang dalawang browser, parehong locker, i-submit nang sabay → isa lang ang papasok (unique index at `FOR UPDATE`).
6. **Approve:** walang date input; assignment may tamang `date_start`, `date_end` (semester end), `rate_per_day`, `total_fee`; locker **Assigned**.
7. **Fee:** halimbawa: semester end 2026-12-19, approve sa 2026-12-10 → 10 araw × ₱5.00 = ₱50.00 (kasama ang parehong dulo).
8. **Rate change:** palitan ang rate sa settings → luma pang assignment, hindi nagbago ang fee.
9. **Reject / Cancel:** locker bumabalik sa **Available**.
10. **Ended semester:** hindi puwedeng mag-request o mag-approve ng semester na tapos na.
11. **Expiry:** ilagay ang `date_end` sa nakaraan (test lang) → assignment at locker nagiging **Expired**; Maintenance ay makikita ito sa Expired filter; Administrator ang makakapag-release.
12. **Maintenance:** Available ↔ Under Maintenance gumagana; sa Reserved/Assigned ay blocked at nasa log.
13. **Access:** Student na magbubukas ng `/admin` → 403 at may log na "access_denied".
14. **Rollback:** pilitin ang error sa gitna ng approve (hal. pansamantalang mali ang column name) → walang na-save na kalahati.

## 11. Mga assumption na kailangang i-confirm ng grupo

- Rate na **₱5.00/day** para sa lahat ng role.
- **Prorated**: kapag nag-approve sa gitna ng sem, remaining days lang ang bayad (kasama ang approval day at ang huling araw).
- **Walang refund** kapag maagang na-release.
- **Isang semester lang** bawat assignment; bagong request para sa susunod.
- Ang semester dates sa `seed.py` ay **dummy**. Ilagay ang totoong academic calendar.
