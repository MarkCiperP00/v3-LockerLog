# config.py
import os
import getpass
import mysql.connector

SECRET_KEY = os.environ.get("SECRET_KEY", "change-this-in-production")
DB_HOST, DB_USER, DB_NAME = "localhost", "root", "lockerlog"


def _db_password():
    """Ask for the MySQL password once per run.

    The password is checked against the server and stored in this process's
    environment, so the Flask debug reloader (a child process) and anything
    else started from this run reuse it without asking again.
    """
    password = os.environ.get("DB_PASSWORD", "")
    for _ in range(4):
        try:
            mysql.connector.connect(host=DB_HOST, user=DB_USER, password=password).close()
            os.environ["DB_PASSWORD"] = password
            return password
        except mysql.connector.Error as e:
            if e.errno != 1045:          # not "Access denied" (e.g. server not running)
                raise
            password = getpass.getpass(f"MySQL password for {DB_USER}@{DB_HOST}: ")
    raise SystemExit("Too many wrong MySQL passwords.")


DB = dict(host=DB_HOST, user=DB_USER, password=_db_password(), database=DB_NAME)
