# LockerLog – Locker Rental and Tracking System

Flask + Jinja2 + Tailwind CSS + JavaScript, with MySQL (8.0.16 or later).

## Run

```bash
python -m venv venv
venv\Scripts\activate            # Linux/Mac: source venv/bin/activate
pip install -r requirements.txt
mysql -u root -p < schema.sql    # creates the "lockerlog" database
# edit config.py (or set DB_PASSWORD and SECRET_KEY as environment variables)
python seed.py                   # 210 lockers, sample semesters, sample accounts
flask --app app run --debug      # open http://127.0.0.1:5000
```

Sample accounts (from seed.py): `2025-2-00001` / `Student#123`, `EMP-0001` / `Prof#12345`, `MNT-0001` / `Maint#12345`, `ADM-0001` / `Admin#12345`.

## Structure

| Path | Purpose |
|---|---|
| `app.py` | Flask routes and role checks |
| `models.py` | User, Borrower, Student, ProfessorStaff, Maintenance, Administrator (OOP, polymorphism) |
| `services/rentals.py` | Submit, approve, reject, cancel, release, expiry, maintenance (transactions) |
| `services/fees.py` | Daily rate and fee computation |
| `db.py`, `config.py` | MySQL connection and settings |
| `schema.sql`, `seed.py` | Tables and starting data |
| `templates/` | HTML (Jinja2) pages styled with Tailwind classes |
| `static/css/app.css`, `static/js/app.js` | Custom CSS and JavaScript (fee preview, confirm dialogs) |
| `docs/` | Proposal PDF and activity diagram |

## Before submitting

- This code was checked with a stand-in database only (all pages render, and role checks and the fee formula work). It has **not** been run against a real MySQL server yet. Run the test checklist in `docs/LockerLog_Code_Guide_MySQL.md`.
- Semester dates in `seed.py` are dummy. Put in the real academic calendar.
- `base.html` loads Tailwind from the Play CDN (development only). For the final version, build a CSS file with the Tailwind CLI and link it instead.
- Assumptions to confirm: ₱5.00 per day, prorated fee, no refund, one semester per assignment.
