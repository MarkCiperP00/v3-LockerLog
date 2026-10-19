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
