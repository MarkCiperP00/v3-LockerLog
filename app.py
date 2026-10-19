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


# ---------- Administrator: lockers and log ----------
@app.route("/admin/lockers", methods=["GET", "POST"])
@needs("manage_lockers")
def admin_lockers():
    import mysql.connector
    rentals.expire_assignments()
    db = get_db()
    if request.method == "POST":
        action, lid = request.form["action"], request.form["locker_id"].strip()
        cur = db.cursor()
        try:
            if action == "add":
                cur.execute("INSERT INTO lockers (locker_id, building, floor) VALUES (%s,%s,%s)",
                            (lid, request.form["building"], request.form["floor"]))
            elif action == "edit":
                cur.execute("UPDATE lockers SET building=%s, floor=%s WHERE locker_id=%s",
                            (request.form["building"], request.form["floor"], lid))
            elif action == "delete":
                cur.execute("DELETE FROM lockers WHERE locker_id=%s AND status='Available'", (lid,))
                if cur.rowcount == 0:
                    raise RuleError("Only an Available locker can be removed")
            db.commit()
            rentals.log_action(g.user.school_id, f"locker_{action}", lid)
            flash(f"Locker {action} done.")
        except mysql.connector.IntegrityError:
            db.rollback()
            flash("Cannot save: duplicate locker ID, or the locker already has history.")
        except RuleError as e:
            db.rollback()
            flash(str(e))
        finally:
            cur.close()
        return redirect("/admin/lockers")
    where, params = ["1=1"], []
    for col in ("building", "floor", "status"):
        if request.args.get(col):
            where.append(f"l.{col}=%s"); params.append(request.args[col])
    rows = query("SELECT l.*, a.assignment_id, a.school_id AS holder, a.date_end "
                 "FROM lockers l LEFT JOIN assignments a ON a.locker_id=l.locker_id "
                 "AND a.status IN ('Active','Expired') "
                 f"WHERE {' AND '.join(where)} ORDER BY l.building, l.floor, l.locker_id", params)
    return render_template("admin/lockers.html", lockers=rows)


@app.route("/admin/log")
@needs("view_activity_log")
def admin_log():
    rows = query("SELECT * FROM activity_log ORDER BY logged_at DESC LIMIT 200")
    return render_template("admin/log.html", log=rows)


@app.errorhandler(403)
def forbidden(e):
    return render_template("403.html"), 403


@app.context_processor
def inject_user():
    return {"me": current_user()}


if __name__ == "__main__":
    app.run(debug=True)
