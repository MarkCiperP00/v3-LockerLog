# LockerLog – Locker Rental and Tracking System

LockerLog is a web application for renting and tracking school lockers. Students and staff can request an available locker, administrators approve or reject requests, and maintenance staff can mark lockers as unavailable. Every action is recorded in an activity log.

**Built with:** Python (Flask), Jinja2, Tailwind CSS, JavaScript, MySQL 8.0.16+
**Start Development in October 2026**
---

## Features

- Browse lockers by building and floor (COECSA, Sotero, JPL – 210 lockers in total)
- Submit, view, and cancel locker rental requests
- Automatic fee computation (prorated daily rate)
- Admin dashboard to approve or reject requests, release lockers, and change the daily rate
- Maintenance page to mark lockers as *Under Maintenance*
- Role-based access (Student, Professor/Staff, Maintenance, Administrator)
- Activity log, including blocked attempts
- Business rules enforced at the database level (for example, one pending request per user)

---

## Requirements

| Software | Version | Download |
|---|---|---|
| Python | 3.10 or newer | https://www.python.org *(tick "Add Python to PATH" when installing)* |
| MySQL Server | 8.0.16 or newer | https://dev.mysql.com/downloads/installer/ |
| Visual Studio Code | Any recent version | https://code.visualstudio.com |

This guide assumes MySQL runs locally with the `root` user and **no password**. If your MySQL has a password, see [Using a MySQL password](#using-a-mysql-password).

---

## Installation

Run all steps in the **VS Code terminal**, in order.

**1. Open the project in VS Code**

Go to **File → Open Folder** and select the `lockerlog` folder. Then open the terminal with **Terminal → New Terminal** (shortcut: `` Ctrl + ` ``). The terminal opens inside the project folder, so no `cd` is needed.

> The commands below are for **PowerShell**, the default terminal on Windows. If the terminal shows a different shell, click the dropdown next to the **+** in the terminal panel and choose **PowerShell**.

**2. Install the dependencies**

```powershell
pip install -r requirements.txt
```

**3. Create the database**

```powershell
& "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe" -u root -e "source schema.sql"
```

**4. Load the starting data** (210 lockers, 2 semesters, 4 sample accounts)

```powershell
python seed.py
```

The terminal should print `Seeded.`

**5. Start the application**

```powershell
flask --app app run --debug
```

Open **http://127.0.0.1:5000** in your browser (or `Ctrl + Click` the link in the terminal). Keep the terminal running while you use the app, and press `Ctrl + C` in the terminal to stop it. To run other commands while the app is running, open a second terminal with the **+** button.

---

## Sample Accounts

| Role | School ID | Password |
|---|---|---|
| Administrator | `ADM-0001` | `Admin#12345` |
| Student | `2025-2-00001` | `Student#123` |
| Professor/Staff | `EMP-0001` | `Prof#12345` |
| Maintenance | `MNT-0001` | `Maint#12345` |

---

## Quick Demo

1. Log in as the **Student**, choose an available locker, and submit a request.
2. Log out and log in as the **Administrator**.
3. Open **Requests** and approve the request.
4. Open the **Activity Log** to see the recorded actions.

---

## Using a MySQL Password

If your MySQL `root` user has a password:

1. In Step 3, add `-p` after `-u root` and enter the password when prompted.
2. In Step 4 and Step 5, the terminal asks `MySQL password for root@localhost:` once. Type the password (nothing is shown while typing) and press Enter. If it is wrong, it asks again.

The password is asked once each time you start the app. To skip the prompt for the rest of a terminal session, set it beforehand:

```powershell
$env:DB_PASSWORD = 'your-password'
```

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `Access denied for user 'root'` | Wrong MySQL password. Restart the app and type it again at the prompt. See [Using a MySQL password](#using-a-mysql-password). |
| `Can't connect to MySQL server` | MySQL is not running. Start it from `services.msc` (usually named `MySQL80`). |
| `Unknown database 'lockerlog'` | Repeat Step 3. |
| `ModuleNotFoundError` | Repeat Step 2. |
| `flask` is not recognized | Run `python -m flask --app app run --debug` instead. |
| Terminal is not in the project folder | Use **File → Open Folder** and select the `lockerlog` folder, then open a new terminal. |
| `python` is not recognized | Reinstall Python and tick "Add Python to PATH", then restart VS Code. |
| Page appears unstyled | Check your internet connection. Tailwind CSS is loaded from a CDN. |
| Invalid login with the correct password | The seed did not run. Repeat Step 4. |

---

## Project Structure

| Path | Purpose |
|---|---|
| `app.py` | Flask routes and role checks |
| `models.py` | User classes: Student, ProfessorStaff, Maintenance, Administrator |
| `services/rentals.py` | Request, approval, cancellation, release, expiry, and maintenance logic (database transactions) |
| `services/fees.py` | Daily rate and fee computation |
| `db.py`, `config.py` | Database connection and settings |
| `schema.sql` | Database tables and constraints |
| `seed.py` | Starting data (lockers, semesters, sample accounts) |
| `templates/` | HTML pages (Jinja2 with Tailwind classes) |
| `static/` | Custom CSS and JavaScript |
| `docs/` | Proposal, code guide, and activity diagram |

---

## Notes and Assumptions

- The semester dates in `seed.py` are placeholders. Replace them with the real academic calendar.
- The rental fee is ₱5.00 per day, counted from the approval date until the end of the semester. Fees are non-refundable, and each assignment covers one semester.
- Tailwind CSS is loaded through the Play CDN, which is intended for development. For production, build a static CSS file with the Tailwind CLI.
- The sample accounts and the empty database password are for local development only. Do not use them in a deployed environment.
