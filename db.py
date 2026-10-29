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
