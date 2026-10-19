import uuid
from datetime import date
import mysql.connector
from db import get_db, log_action
from services.fees import get_rate_per_day, compute_assignment

class RuleError(Exception):
    """Raised when a business rule blocks an action."""

def _id(prefix):
    return f"{prefix}-{uuid.uuid4().hex[:8]}"

def _begin(db):
    """Close any read-only transaction left open by earlier SELECTs, then start a fresh one."""
    if db.in_transaction:
        db.rollback()
    db.start_transaction()

def submit_request(user, locker_id, semester_id):
    db = get_db()
    cur = db.cursor(dictionary=True)
    try:
        _begin(db)
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
        _begin(db)
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
        _begin(db)
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
        _begin(db)
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